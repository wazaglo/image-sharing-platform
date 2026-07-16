const CONFIG = {
  region: 'us-east-1',
  userPoolId: '',
  clientId: '',
  apiUrl: '',
  cognitoUrl: '',
};

let state = {
  currentFolder: 'root',
  pendingUploads: 0,
  allFolders: [],
  selectedFiles: new Set(),
  currentBreadcrumb: [],
  currentSort: 'name',
  currentFilter: 'all',
  currentUser: null,
  currentToken: null,
  renameTarget: null,
  moveTarget: null,
  shareTarget: null,
};

function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
  document.getElementById('authPages').style.display = 'none';

  if (['login', 'signup', 'verify', 'forgotPassword', 'resetPassword'].includes(page)) {
    document.getElementById('authPages').style.display = 'block';
    document.querySelectorAll('.auth-page').forEach(p => p.style.display = 'none');
    document.getElementById(page + 'Page').style.display = 'flex';
    return;
  }

  document.getElementById('mainApp').style.display = 'block';

  const handlers = {
    dashboard: () => { document.getElementById('dashboardPage').style.display = 'block'; loadDashboard(); },
    folder: () => { document.getElementById('folderPage').style.display = 'block'; loadFolder(state.currentFolder); },
    search: () => { document.getElementById('searchPage').style.display = 'block'; },
    sharedWithMe: () => { document.getElementById('sharedWithMePage').style.display = 'block'; loadSharedWithMe(); },
    trash: () => { document.getElementById('trashPage').style.display = 'block'; loadTrash(); },
    admin: () => { document.getElementById('adminPage').style.display = 'block'; adminListUsers(); },
    account: () => { document.getElementById('accountPage').style.display = 'block'; loadAccount(); },
  };

  (handlers[page] || handlers.dashboard)();
}

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('pixel-theme', next);
}

const COGNITO_DOMAIN = CONFIG.cognitoUrl || `https://pixel-auth.auth.${CONFIG.region}.amazoncognito.com`;

function signup() {
  const email = document.getElementById('signupEmail').value.trim();
  const password = document.getElementById('signupPassword').value;
  const confirm = document.getElementById('signupConfirm').value;

  if (!email || !password) return showError('signupError', 'Email and password required');
  if (password !== confirm) return showError('signupError', 'Passwords do not match');
  if (password.length < 8) return showError('signupError', 'Password must be at least 8 characters');

  fetch(`${CONFIG.cognitoUrl}/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      document.getElementById('verifyEmailDisplay').textContent = `Code sent to ${email}`;
      showPage('verify');
    } else {
      showError('signupError', data.error || 'Signup failed');
    }
  })
  .catch(() => showError('signupError', 'Network error'));
}

function verify() {
  const code = document.getElementById('verifyCode').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
  if (!code) return showError('verifyError', 'Code required');

  fetch(`${CONFIG.cognitoUrl}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showPage('login');
    } else {
      showError('verifyError', data.error || 'Verification failed');
    }
  })
  .catch(() => showError('verifyError', 'Network error'));
}

function login() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  if (!email || !password) return showError('loginError', 'Email and password required');

  showLoading(true);
  fetch(`${CONFIG.apiUrl}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  .then(r => r.json())
  .then(data => {
    showLoading(false);
    if (data.success && data.token) {
      state.currentUser = { email, sub: data.sub || email };
      state.currentToken = data.token;
      localStorage.setItem('pixel-token', data.token);
      localStorage.setItem('pixel-user', JSON.stringify(state.currentUser));
      checkAdmin();
      showPage('dashboard');
    } else {
      showError('loginError', data.error || 'Login failed');
    }
  })
  .catch(() => { showLoading(false); showError('loginError', 'Network error'); });
}

function forgotPassword() {
  const email = document.getElementById('forgotEmail').value.trim();
  if (!email) return showError('forgotError', 'Email required');

  fetch(`${CONFIG.cognitoUrl}/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      document.getElementById('resetEmail').value = email;
      showPage('resetPassword');
    } else {
      showError('forgotError', data.error || 'Failed');
    }
  })
  .catch(() => showError('forgotError', 'Network error'));
}

function resetPassword() {
  const email = document.getElementById('resetEmail').value.trim();
  const code = document.getElementById('resetCode').value.trim();
  const password = document.getElementById('resetPassword').value;
  if (!code || !password) return showError('resetError', 'All fields required');

  fetch(`${CONFIG.cognitoUrl}/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code, password }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showPage('login');
    } else {
      showError('resetError', data.error || 'Failed');
    }
  })
  .catch(() => showError('resetError', 'Network error'));
}

function signOut() {
  state.currentToken = null;
  state.currentUser = null;
  localStorage.removeItem('pixel-token');
  localStorage.removeItem('pixel-user');
  showPage('login');
  clearAuthInputs();
}

function clearAuthInputs() {
  ['login', 'signup', 'verify', 'forgot', 'reset'].forEach(prefix => {
    const el = document.getElementById(prefix + 'Error');
    if (el) el.style.display = 'none';
  });
}

function showError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}

async function apiCall(action, payload = {}) {
  const token = state.currentToken || localStorage.getItem('pixel-token');
  const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
  const body = JSON.stringify({ action, ...payload });

  const resp = await fetch(CONFIG.apiUrl, { method: 'POST', headers, body });
  return resp.json();
}

function showLoading(on) {
  document.getElementById('loadingOverlay').style.display = on ? 'flex' : 'none';
}

async function loadDashboard() {
  showLoading(true);
  const data = await apiCall('listFolders');
  showLoading(false);

  if (data.success) {
    state.allFolders = data.folders || [];
    renderDashboardFolders(state.allFolders);
  }
}

function renderDashboardFolders(folders) {
  const container = document.getElementById('dashboardFolders');
  if (!folders.length) {
    container.innerHTML = '<div class="empty-state">No folders yet. Create your first folder!</div>';
    return;
  }
  container.innerHTML = folders.map(f => `
    <div class="folder-card" ondblclick="openFolder('${f.folderId}')">
      <div class="folder-icon">📁</div>
      <div class="folder-name">${escHtml(f.name)}</div>
      <div class="folder-actions">
        <button onclick="event.stopPropagation(); openFolder('${f.folderId}')" title="Open">📂</button>
        <button onclick="event.stopPropagation(); showRenameFolderModal('${f.folderId}','${escHtml(f.name)}')" title="Rename">✏️</button>
        <button onclick="event.stopPropagation(); deleteFolder('${f.folderId}')" title="Delete">🗑️</button>
        <button onclick="event.stopPropagation(); showShareModal('${f.folderId}')" title="Share">🔗</button>
      </div>
    </div>
  `).join('');
}

function createFolder() {
  const name = document.getElementById('newFolderName').value.trim();
  if (!name) return;

  showLoading(true);
  apiCall('createFolder', { name, parentId: state.currentFolder })
    .then(data => {
      showLoading(false);
      if (data.success) {
        closeModal('createFolderModal');
        document.getElementById('newFolderName').value = '';
        loadDashboard();
        if (document.getElementById('folderPage').style.display !== 'none') {
          loadFolder(state.currentFolder);
        }
      }
    })
    .catch(() => showLoading(false));
}

function deleteFolder(folderId) {
  if (!confirm('Delete this folder and all contents?')) return;
  showLoading(true);
  apiCall('deleteFolder', { folderId, recursive: true })
    .then(data => {
      showLoading(false);
      if (data.success) loadDashboard();
    })
    .catch(() => showLoading(false));
}

function showRenameFolderModal(folderId, currentName) {
  state.renameTarget = folderId;
  document.getElementById('renameFolderInput').value = currentName;
  openModal('renameFolderModal');
}

function renameFolder() {
  const name = document.getElementById('renameFolderInput').value.trim();
  if (!name || !state.renameTarget) return;

  showLoading(true);
  apiCall('renameFolder', { folderId: state.renameTarget, name })
    .then(data => {
      showLoading(false);
      if (data.success) {
        closeModal('renameFolderModal');
        state.renameTarget = null;
        loadDashboard();
      }
    })
    .catch(() => showLoading(false));
}

async function loadFolder(folderId) {
  state.currentFolder = folderId;
  showLoading(true);
  const [folderData, filesData] = await Promise.all([
    apiCall('listFolders', { parentId: folderId }),
    apiCall('listFiles', { folderId }),
  ]);
  showLoading(false);

  if (folderData.success && filesData.success) {
    state.allFolders = folderData.folders || [];
    renderBreadcrumb(folderId);
    renderSubfolders(folderData.folders);
    renderFiles(applySortAndFilter(filesData.files || []));
  }
}

function renderBreadcrumb(folderId) {
  const container = document.getElementById('breadcrumb');
  const trail = [{ id: 'root', name: 'My Files' }];

  function findPath(id, folders) {
    for (const f of folders) {
      if (f.folderId === id) {
        const parent = f.parentId && f.parentId !== 'root' ? findPath(f.parentId, state.allFolders) : [];
        return [...parent, f];
      }
    }
    return [];
  }

  if (folderId !== 'root') {
    const path = findPath(folderId, state.allFolders);
    trail.push(...path);
  }

  state.currentBreadcrumb = trail;
  container.innerHTML = trail.map((item, i) => `
    <span class="breadcrumb-item ${i === trail.length - 1 ? 'active' : ''}"
          onclick="${i < trail.length - 1 ? `openFolder('${item.id}')` : ''}">
      ${escHtml(item.name)}
    </span>
    ${i < trail.length - 1 ? '<span class="breadcrumb-sep">/</span>' : ''}
  `).join('');
}

function renderSubfolders(folders) {
  const section = document.getElementById('subfoldersSection');
  const grid = document.getElementById('subfoldersGrid');

  if (!folders || !folders.length) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';
  grid.innerHTML = folders.map(f => `
    <div class="folder-card" ondblclick="openFolder('${f.folderId}')">
      <div class="folder-icon">📁</div>
      <div class="folder-name">${escHtml(f.name)}</div>
      <div class="folder-actions">
        <button onclick="event.stopPropagation(); openFolder('${f.folderId}')" title="Open">📂</button>
        <button onclick="event.stopPropagation(); showRenameFolderModal('${f.folderId}','${escHtml(f.name)}')" title="Rename">✏️</button>
        <button onclick="event.stopPropagation(); deleteFolder('${f.folderId}')" title="Delete">🗑️</button>
        <button onclick="event.stopPropagation(); showShareModal('${f.folderId}')" title="Share">🔗</button>
      </div>
    </div>
  `).join('');
}

function openFolder(folderId) {
  state.currentFolder = folderId;
  showPage('folder');
}

function triggerUpload() {
  document.getElementById('fileInput').click();
}

function triggerFolderUpload() {
  document.getElementById('folderInput').click();
}

async function handleFileInput(event) {
  const files = event.target.files;
  if (!files.length) return;
  await uploadFiles(files);
  event.target.value = '';
}

async function handleFolderInput(event) {
  const files = event.target.files;
  if (!files.length) return;
  await uploadFolderFiles(files);
  event.target.value = '';
}

async function uploadFiles(fileList) {
  state.pendingUploads += fileList.length;
  showProgress(true, 0);

  let completed = 0;
  const total = fileList.length;

  for (const file of fileList) {
    try {
      const data = await apiCall('uploadFile', {
        fileName: file.name,
        contentType: file.type || 'application/octet-stream',
        size: file.size,
        folderId: state.currentFolder,
      });

      if (data.success && data.uploadUrl) {
        await fetch(data.uploadUrl, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type || 'application/octet-stream' },
        });
      }
    } catch (e) {
      console.error('Upload failed:', file.name, e);
    }

    completed++;
    showProgress(true, Math.round((completed / total) * 100));
  }

  state.pendingUploads -= total;
  showProgress(false);
  loadFolder(state.currentFolder);
}

async function uploadFolderFiles(files) {
  const fileMap = {};
  for (const file of files) {
    const path = file.webkitRelativePath || file.name;
    const parts = path.split('/');
    const fileName = parts.pop();
    const folderPath = parts.slice(1).join('/');

    if (!fileMap[folderPath]) fileMap[folderPath] = [];
    fileMap[folderPath].push({ file, name: fileName });
  }

  const folderPaths = Object.keys(fileMap);

  async function ensureFolders(paths) {
    const created = {};
    for (const folderPath of paths) {
      if (!folderPath) { created[''] = state.currentFolder; continue; }
      const parts = folderPath.split('/');
      let parentId = state.currentFolder;
      let currentPath = '';
      for (const part of parts) {
        currentPath = currentPath ? `${currentPath}/${part}` : part;
        const existing = state.allFolders.find(f => f.name === part && f.parentId === parentId);
        if (existing) {
          parentId = existing.folderId;
        } else {
          const data = await apiCall('createFolder', { name: part, parentId });
          if (data.success && data.folder) {
            parentId = data.folder.folderId;
            state.allFolders.push(data.folder);
          }
        }
        created[currentPath] = parentId;
      }
    }
    return created;
  }

  const folderIds = await ensureFolders(folderPaths);

  const allFiles = [];
  for (const folderPath of folderPaths) {
    const fid = folderPath ? folderIds[folderPath] : state.currentFolder;
    for (const item of fileMap[folderPath]) {
      allFiles.push({ file: item.file, name: item.name, folderId: fid });
    }
  }

  state.pendingUploads += allFiles.length;
  showProgress(true, 0);
  let completed = 0;

  for (const { file, name, folderId } of allFiles) {
    try {
      const data = await apiCall('uploadFile', {
        fileName: name,
        contentType: file.type || 'application/octet-stream',
        size: file.size,
        folderId,
      });
      if (data.success && data.uploadUrl) {
        await fetch(data.uploadUrl, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type || 'application/octet-stream' },
        });
      }
    } catch (e) {
      console.error('Upload failed:', name, e);
    }
    completed++;
    showProgress(true, Math.round((completed / allFiles.length) * 100));
  }

  state.pendingUploads -= allFiles.length;
  showProgress(false);
  loadFolder(state.currentFolder);
}

function handleDragOver(e) { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }
function handleDragLeave(e) { e.preventDefault(); e.currentTarget.classList.remove('drag-over'); }

async function handleDrop(e) {
  e.preventDefault();
  const area = e.currentTarget;
  area.classList.remove('drag-over');

  const items = e.dataTransfer.items;
  if (!items || !items.length) return;

  const files = [];
  for (const item of items) {
    if (item.webkitGetAsEntry) {
      const entry = item.webkitGetAsEntry();
      if (entry) {
        const traversed = await traverseEntry(entry, '');
        files.push(...traversed);
      }
    } else if (item.getAsFile) {
      const file = item.getAsFile();
      if (file) files.push({ file, path: file.name });
    }
  }

  if (!files.length) return;

  const fileMap = {};
  for (const { file, path } of files) {
    const parts = path.split('/');
    const fileName = parts.pop();
    const folderPath = parts.join('/');
    if (!fileMap[folderPath]) fileMap[folderPath] = [];
    fileMap[folderPath].push({ file, name: fileName });
  }

  const folderPaths = Object.keys(fileMap);

  async function ensureFolders(paths) {
    const created = {};
    for (const folderPath of paths) {
      if (!folderPath) { created[''] = state.currentFolder; continue; }
      const parts = folderPath.split('/');
      let parentId = state.currentFolder;
      let currentPath = '';
      for (const part of parts) {
        currentPath = currentPath ? `${currentPath}/${part}` : part;
        const existing = state.allFolders.find(f => f.name === part && f.parentId === parentId);
        if (existing) {
          parentId = existing.folderId;
        } else {
          const data = await apiCall('createFolder', { name: part, parentId });
          if (data.success && data.folder) {
            parentId = data.folder.folderId;
            state.allFolders.push(data.folder);
          }
        }
        created[currentPath] = parentId;
      }
    }
    return created;
  }

  const folderIds = await ensureFolders(folderPaths);

  state.pendingUploads += files.length;
  showProgress(true, 0);
  let completed = 0;

  for (const folderPath of folderPaths) {
    const fid = folderPath ? folderIds[folderPath] : state.currentFolder;
    for (const { file, name } of fileMap[folderPath]) {
      try {
        const data = await apiCall('uploadFile', {
          fileName: name, contentType: file.type || 'application/octet-stream',
          size: file.size, folderId: fid,
        });
        if (data.success && data.uploadUrl) {
          await fetch(data.uploadUrl, {
            method: 'PUT', body: file,
            headers: { 'Content-Type': file.type || 'application/octet-stream' },
          });
        }
      } catch (e) { console.error('Upload failed:', name, e); }
      completed++;
      showProgress(true, Math.round((completed / files.length) * 100));
    }
  }

  state.pendingUploads -= files.length;
  showProgress(false);
  loadFolder(state.currentFolder);
}

function traverseEntry(entry, path) {
  return new Promise((resolve) => {
    if (entry.isFile) {
      entry.file(file => {
        resolve([{ file, path: path ? `${path}/${entry.name}` : entry.name }]);
      }, () => resolve([]));
    } else if (entry.isDirectory) {
      const dirReader = entry.createReader();
      const entries = [];
      const readEntries = () => {
        dirReader.readEntries(results => {
          if (results.length) {
            entries.push(...results);
            readEntries();
          } else {
            Promise.all(entries.map(e => traverseEntry(e, path ? `${path}/${entry.name}` : entry.name)))
              .then(results => resolve(results.flat()));
          }
        }, () => resolve([]));
      };
      readEntries();
    } else {
      resolve([]);
    }
  });
}

function renderFiles(files) {
  const grid = document.getElementById('fileGrid');
  if (!files || !files.length) {
    grid.innerHTML = '<div class="empty-state">No files in this folder</div>';
    return;
  }

  grid.innerHTML = files.map(f => {
    const selected = state.selectedFiles.has(f.fileId);
    return `
      <div class="file-card ${selected ? 'selected' : ''}"
           onclick="toggleFileSelect('${f.fileId}')"
           ondblclick="previewFile('${f.fileId}')">
        <div class="file-check">
          <input type="checkbox" ${selected ? 'checked' : ''} onchange="toggleFileSelect('${f.fileId}')">
        </div>
        <div class="file-thumb">
          ${f.thumbnailUrl
            ? `<img src="${f.thumbnailUrl}" alt="${escHtml(f.fileName)}" loading="lazy">`
            : `<span class="file-icon">${getFileIcon(f.contentType, f.fileName)}</span>`
          }
        </div>
        <div class="file-name" title="${escHtml(f.fileName)}">${escHtml(f.fileName)}</div>
        <div class="file-meta">
          <span>${formatBytes(f.size)}</span>
          <span>${f.contentType ? f.contentType.split('/').pop().toUpperCase() : 'N/A'}</span>
        </div>
        <div class="file-actions">
          <button onclick="event.stopPropagation(); downloadFile('${f.fileId}')" title="Download">⬇️</button>
          <button onclick="event.stopPropagation(); showRenameFileModal('${f.fileId}','${escHtml(f.fileName)}')" title="Rename">✏️</button>
          <button onclick="event.stopPropagation(); showMoveFileModal('${f.fileId}')" title="Move">📂</button>
          <button onclick="event.stopPropagation(); trashFile('${f.fileId}')" title="Trash">🗑️</button>
        </div>
      </div>
    `;
  }).join('');
}

async function downloadFile(fileId) {
  const data = await apiCall('listFiles', { folderId: state.currentFolder });
  if (data.success) {
    const file = data.files.find(f => f.fileId === fileId);
    if (file && file.presignedUrl) {
      window.open(file.presignedUrl, '_blank');
    }
  }
}

function showRenameFileModal(fileId, currentName) {
  state.renameTarget = fileId;
  document.getElementById('renameFileInput').value = currentName;
  openModal('renameFileModal');
}

function renameFile() {
  const name = document.getElementById('renameFileInput').value.trim();
  if (!name || !state.renameTarget) return;

  showLoading(true);
  apiCall('renameFile', { fileId: state.renameTarget, fileName: name })
    .then(data => {
      showLoading(false);
      if (data.success) {
        closeModal('renameFileModal');
        state.renameTarget = null;
        loadFolder(state.currentFolder);
      }
    })
    .catch(() => showLoading(false));
}

async function showMoveFileModal(fileId) {
  state.moveTarget = fileId;
  const data = await apiCall('listFolders');
  if (data.success) {
    const select = document.getElementById('moveFolderSelect');
    select.innerHTML = '<option value="root">My Files</option>' +
      data.folders.map(f => `<option value="${f.folderId}">${escHtml(f.name)}</option>`).join('');
    openModal('moveFileModal');
  }
}

function moveFile() {
  const targetId = document.getElementById('moveFolderSelect').value;
  if (!state.moveTarget) return;

  showLoading(true);
  apiCall('moveFile', { fileId: state.moveTarget, targetFolderId: targetId })
    .then(data => {
      showLoading(false);
      if (data.success) {
        closeModal('moveFileModal');
        state.moveTarget = null;
        loadFolder(state.currentFolder);
      }
    })
    .catch(() => showLoading(false));
}

function toggleFileSelect(fileId) {
  if (state.selectedFiles.has(fileId)) {
    state.selectedFiles.delete(fileId);
  } else {
    state.selectedFiles.add(fileId);
  }
  updateBatchBar();
  loadFolder(state.currentFolder);
}

function clearSelection() {
  state.selectedFiles.clear();
  updateBatchBar();
  loadFolder(state.currentFolder);
}

function updateBatchBar() {
  const bar = document.getElementById('batchBar');
  const count = state.selectedFiles.size;
  if (count > 0) {
    bar.style.display = 'flex';
    document.getElementById('selectedCount').textContent = `${count} selected`;
  } else {
    bar.style.display = 'none';
  }
}

async function batchDelete() {
  if (!state.selectedFiles.size || !confirm(`Delete ${state.selectedFiles.size} file(s)?`)) return;

  showLoading(true);
  for (const fileId of state.selectedFiles) {
    await apiCall('trashFile', { fileId });
  }
  showLoading(false);
  state.selectedFiles.clear();
  updateBatchBar();
  loadFolder(state.currentFolder);
}

function trashFile(fileId) {
  if (!confirm('Move to trash?')) return;
  showLoading(true);
  apiCall('trashFile', { fileId })
    .then(data => {
      showLoading(false);
      if (data.success) loadFolder(state.currentFolder);
    })
    .catch(() => showLoading(false));
}

function showShareModal(folderId) {
  state.shareTarget = folderId;
  document.getElementById('shareLinkOutput').value = '';
  document.getElementById('sharePinInput').value = '';
  document.getElementById('shareExpiryInput').value = '';
  document.getElementById('shareEmailsInput').value = '';
  openModal('shareModal');
}

async function generateShareLink() {
  const pin = document.getElementById('sharePinInput').value.trim();
  const expiry = document.getElementById('shareExpiryInput').value;
  const permission = document.getElementById('sharePermissionSelect').value;
  const emailsRaw = document.getElementById('shareEmailsInput').value.trim();
  const sharedWithEmails = emailsRaw ? emailsRaw.split(',').map(e => e.trim()).filter(Boolean) : [];

  showLoading(true);
  const data = await apiCall('generateShareLink', {
    folderId: state.shareTarget,
    pin,
    expiry: expiry ? new Date(expiry).toISOString() : '',
    permission,
    sharedWithEmails,
  });
  showLoading(false);

  if (data.success) {
    document.getElementById('shareLinkOutput').value = data.shareUrl;
  }
}

function copyShareLink() {
  const input = document.getElementById('shareLinkOutput');
  input.select();
  navigator.clipboard.writeText(input.value);
}

function doSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) return;

  showLoading(true);
  apiCall('searchFiles', { query })
    .then(data => {
      showLoading(false);
      if (data.success) {
        showPage('search');
        renderFiles(data.files || []);
      }
    })
    .catch(() => showLoading(false));
}

function setSort(value) {
  state.currentSort = value;
  loadFolder(state.currentFolder);
}

function setFilter(value) {
  state.currentFilter = value;
  loadFolder(state.currentFolder);
}

function applySortAndFilter(files) {
  let filtered = [...files];

  if (state.currentFilter !== 'all') {
    const filterMap = {
      image: 'image/',
      video: 'video/',
      audio: 'audio/',
      document: 'pdf',
      other: '',
    };
    const prefix = filterMap[state.currentFilter];
    if (state.currentFilter === 'other') {
      filtered = files.filter(f => {
        const ct = (f.contentType || '');
        return !ct.startsWith('image/') && !ct.startsWith('video/') && !ct.startsWith('audio/') && !ct.includes('pdf');
      });
    } else if (prefix) {
      filtered = files.filter(f => (f.contentType || '').startsWith(prefix) || (f.contentType || '').includes(prefix));
    }
  }

  const sortMap = {
    name: (a, b) => (a.fileName || '').localeCompare(b.fileName || ''),
    date: (a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''),
    size: (a, b) => (b.size || 0) - (a.size || 0),
    type: (a, b) => (a.contentType || '').localeCompare(b.contentType || ''),
  };

  return (sortMap[state.currentSort] || sortMap.name)(filtered);
}

function previewFile(fileId) {
  showLoading(true);
  apiCall('listFiles', { folderId: state.currentFolder })
    .then(data => {
      showLoading(false);
      if (!data.success) return;
      const file = data.files.find(f => f.fileId === fileId);
      if (!file) return;

      const content = document.getElementById('previewContent');
      const ct = file.contentType || '';

      if (ct.startsWith('image/')) {
        content.innerHTML = `<img src="${file.presignedUrl}" alt="${escHtml(file.fileName)}" style="max-width:100%;max-height:80vh;">`;
      } else if (ct.includes('pdf')) {
        content.innerHTML = `<iframe src="${file.presignedUrl}" style="width:100%;height:80vh;" frameborder="0"></iframe>`;
      } else if (ct.startsWith('text/') || ct.includes('json') || ct.includes('javascript')) {
        fetch(file.presignedUrl).then(r => r.text()).then(text => {
          content.innerHTML = `<pre style="max-height:80vh;overflow:auto;background:var(--bg-secondary);padding:1rem;border-radius:8px;white-space:pre-wrap;word-break:break-all;">${escHtml(text)}</pre>`;
        });
      } else if (ct.startsWith('video/')) {
        content.innerHTML = `<video controls style="max-width:100%;max-height:80vh;"><source src="${file.presignedUrl}" type="${ct}"></video>`;
      } else {
        content.innerHTML = `<div style="text-align:center;padding:2rem;"><p>Preview not available for this file type.</p><a href="${file.presignedUrl}" target="_blank" class="btn-primary">Download</a></div>`;
      }
      openModal('previewModal');
    });
}

async function loadSharedWithMe() {
  showLoading(true);
  const data = await apiCall('sharedWithMe');
  showLoading(false);

  const container = document.getElementById('sharedWithMeContent');
  if (!data.success || !data.sharedItems || !data.sharedItems.length) {
    container.innerHTML = '<div class="empty-state">No shares yet</div>';
    return;
  }

  container.innerHTML = data.sharedItems.map(item => `
    <div class="shared-card">
      <div class="shared-header">
        <h3>${escHtml(item.folder.name)}</h3>
        <span class="shared-owner">Shared by: ${escHtml(item.ownerEmail)}</span>
        <span class="shared-perm">${item.share.permission || 'view'}</span>
      </div>
      <div class="file-grid">
        ${item.files.map(f => `
          <div class="file-card" onclick="window.open('${f.presignedUrl}','_blank')">
            <div class="file-thumb">
              ${f.thumbnailUrl
                ? `<img src="${f.thumbnailUrl}" alt="${escHtml(f.fileName)}" loading="lazy">`
                : `<span class="file-icon">${getFileIcon(f.contentType, f.fileName)}</span>`
              }
            </div>
            <div class="file-name">${escHtml(f.fileName)}</div>
            <div class="file-meta"><span>${formatBytes(f.size)}</span></div>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
}

async function loadTrash() {
  showLoading(true);
  const data = await apiCall('listFiles', { folderId: 'root', includeDeleted: true });
  showLoading(false);

  const container = document.getElementById('trashContent');
  if (!data.success) {
    container.innerHTML = '<div class="empty-state">Failed to load trash</div>';
    return;
  }

  const trashed = (data.files || []).filter(f => f.isDeleted);

  if (!trashed.length) {
    container.innerHTML = '<div class="empty-state">Trash is empty</div>';
    return;
  }

  container.innerHTML = trashed.map(f => `
    <div class="file-card">
      <div class="file-thumb">
        <span class="file-icon">${getFileIcon(f.contentType, f.fileName)}</span>
      </div>
      <div class="file-name">${escHtml(f.fileName)}</div>
      <div class="file-meta">
        <span>${formatBytes(f.size)}</span>
        <span>${f.deletedAt ? new Date(f.deletedAt).toLocaleDateString() : ''}</span>
      </div>
      <div class="file-actions">
        <button onclick="restoreFile('${f.fileId}')" title="Restore">♻️</button>
        <button onclick="permanentDeleteFile('${f.fileId}')" title="Delete permanently">🗑️</button>
      </div>
    </div>
  `).join('');
}

async function restoreFile(fileId) {
  showLoading(true);
  const data = await apiCall('restoreFile', { fileId });
  showLoading(false);
  if (data.success) loadTrash();
}

async function emptyTrash() {
  if (!confirm('Permanently delete all trashed files?')) return;
  showLoading(true);
  const data = await apiCall('emptyTrash');
  showLoading(false);
  if (data.success) loadTrash();
}

async function permanentDeleteFile(fileId) {
  if (!confirm('Permanently delete this file?')) return;
  showLoading(true);
  const data = await apiCall('deleteFile', { fileId });
  showLoading(false);
  if (data.success) loadTrash();
}

function checkAdmin() {
  document.getElementById('adminBtn').style.display = 'none';
}

async function adminListUsers() {
  const data = await apiCall('adminListUsers');
  const body = document.getElementById('adminUsersBody');

  if (!data.success) {
    body.innerHTML = '<tr><td colspan="4">Access denied</td></tr>';
    return;
  }

  body.innerHTML = (data.users || []).map(u => `
    <tr>
      <td>${escHtml(u.email)}</td>
      <td>${u.status}</td>
      <td>${u.createdAt ? new Date(u.createdAt).toLocaleDateString() : ''}</td>
      <td><button class="btn-danger btn-small" onclick="adminDeleteUser('${u.sub}')">Delete</button></td>
    </tr>
  `).join('');
}

async function adminDeleteUser(targetSub) {
  if (!confirm('Delete this user?')) return;
  showLoading(true);
  const data = await apiCall('adminDeleteUser', { targetSub });
  showLoading(false);
  if (data.success) adminListUsers();
}

async function loadAccount() {
  const user = state.currentUser || JSON.parse(localStorage.getItem('pixel-user') || '{}');
  if (user.email) document.getElementById('accountEmail').textContent = user.email;
  document.getElementById('updateEmailInput').value = user.email || '';

  const data = await apiCall('stats');
  if (data.success && data.stats) {
    document.getElementById('accountStorage').textContent = formatBytes(data.stats.totalSize || 0);
  }
}

function updateEmail() {
  const email = document.getElementById('updateEmailInput').value.trim();
  if (!email) return;
  alert('Email update feature requires Cognito integration');
}

function changePassword() {
  const oldPw = document.getElementById('changePasswordOld').value;
  const newPw = document.getElementById('changePasswordNew').value;
  if (!oldPw || !newPw) return alert('Both passwords required');
  if (newPw.length < 8) return alert('New password must be at least 8 characters');
  alert('Password change requires Cognito integration');
}

function deleteAccount() {
  if (!confirm('Are you sure? This will permanently delete ALL your data!')) return;
  if (!confirm('This action cannot be undone. Proceed?')) return;
  showLoading(true);
  apiCall('deleteAccount')
    .then(data => {
      showLoading(false);
      if (data.success) signOut();
    })
    .catch(() => showLoading(false));
}

function openModal(id) {
  document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
  document.getElementById(id).style.display = 'none';
}

function showProgress(show, pct) {
  const el = document.getElementById('uploadProgress');
  if (!show) {
    el.style.display = 'none';
    return;
  }
  el.style.display = 'flex';
  document.getElementById('progressFill').style.width = `${pct}%`;
  document.getElementById('progressText').textContent = `${pct}%`;
}

function escHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < sizes.length - 1) { val /= 1024; i++; }
  return `${val.toFixed(1)} ${sizes[i]}`;
}

function getFileIcon(contentType, fileName) {
  if (!contentType) return '📄';
  if (contentType.startsWith('image/')) return '📷';
  if (contentType.startsWith('video/')) return '🎬';
  if (contentType.startsWith('audio/')) return '🎵';
  if (contentType.includes('pdf')) return '📕';
  if (contentType.includes('zip') || contentType.includes('rar') || contentType.includes('tar') || contentType.includes('gzip')) return '📦';
  return '📄';
}

function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch (e) {
    return {};
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const savedTheme = localStorage.getItem('pixel-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);

  const savedToken = localStorage.getItem('pixel-token');
  const savedUser = localStorage.getItem('pixel-user');

  if (savedToken && savedUser) {
    state.currentToken = savedToken;
    state.currentUser = JSON.parse(savedUser);
    checkAdmin();
    showPage('dashboard');
  } else {
    showPage('login');
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
    }
  });

  window.addEventListener('click', e => {
    document.querySelectorAll('.modal').forEach(m => {
      if (e.target === m) m.style.display = 'none';
    });
  });
});

document.getElementById('createFolderModal').addEventListener('keydown', e => {
  if (e.key === 'Enter') createFolder();
});
document.getElementById('renameFolderModal').addEventListener('keydown', e => {
  if (e.key === 'Enter') renameFolder();
});
document.getElementById('renameFileModal').addEventListener('keydown', e => {
  if (e.key === 'Enter') renameFile();
});
