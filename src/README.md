# Source Code

## Overview

The `src/` directory contains all application code divided into backend (Lambda functions) and frontend (web UI).

```
src/
├── backend/
│   ├── lambdas/
│   │   ├── folder_manager/
│   │   ├── upload_handler/
│   │   ├── share_link_generator/
│   │   ├── public_access_handler/
│   │   ├── image_processor/
│   │   └── webdav_handler/
│   └── shared/
│       ├── config.py
│       └── utils.py
└── frontend/
    └── ui/
        ├── index.html
        ├── app.js
        ├── style.css
        └── share.html
```

---

## Backend — Lambda Functions

### 1. FolderManager

- **File**: `backend/lambdas/folder_manager/handler.py`
- **Route**: `POST /folders`
- **Auth**: Cognito user pool
- **Purpose**: Manages all folder operations plus user account management and admin functions

**Actions**:
| Action | Description |
|---|---|
| `create` | Create folder with `parentId` for nesting, creates S3 prefix marker |
| `list` | List all user folders |
| `delete` | Recursively delete folder + all descendants + files + S3 objects |
| `rename` | Update folder name |
| `stats` | Return folder/file counts and total storage size |
| `deleteAccount` | Delete all user data + remove Cognito user |
| `adminListUsers` | (admin only) List all Cognito users |
| `adminDeleteUser` | (admin only) Delete a Cognito user |
| `sharedWithMe` | Scan Shares table for user's email, return shared folder contents |

**Environment Variables**:
| Variable | Description |
|---|---|
| `BUCKET_NAME` | S3 bucket for file storage |
| `FOLDERS_TABLE` | DynamoDB table for folder metadata |
| `FILES_TABLE` | DynamoDB table for file metadata |
| `SHARES_TABLE` | DynamoDB table for share link records |
| `USERS_PREFIX` | S3 prefix for user files (`users/`) |
| `THUMBNAIL_PREFIX` | S3 prefix for thumbnails (`thumbnails/`) |
| `CLOUDFRONT_DOMAIN` | CloudFront distribution domain |
| `LOG_LEVEL` | Logging verbosity |
| `ADMIN_EMAILS` | Comma-separated list of admin email addresses |

**IAM Permissions**: S3 (bucket read/write), DynamoDB (CRUD on all three tables), Cognito (admin user operations)

---

### 2. UploadHandler

- **File**: `backend/lambdas/upload_handler/handler.py`
- **Route**: `POST /folders/{id}/files`
- **Auth**: Cognito user pool
- **Purpose**: File management including upload via presigned URL, search, soft-delete trash

**Actions**:
| Action | Description |
|---|---|
| `upload` (default) | Generate presigned PUT URL, create DynamoDB record, update folder counts |
| `list` | List files in folder (excludes deleted), enriches with download + thumbnail URLs |
| `search` | Scan all user files for name match (excludes deleted) |
| `delete` | Soft delete — copy to `trash/` S3 prefix, mark `isDeleted` in DynamoDB |
| `rename` | Copy S3 object to new key, update DynamoDB, handle thumbnail renames |
| `move` | Copy S3 object to new folder prefix, update DynamoDB, update folder file counts |
| `trash` | List all soft-deleted files for the user |
| `restore` | Copy from `trash/` back to `users/` prefix, remove DynamoDB delete markers |
| `emptyTrash` | Permanently delete all trashed S3 objects + DynamoDB records |

**Upload Flow**:
1. Client POSTs file metadata to the Lambda
2. Lambda returns a presigned S3 PUT URL
3. Client PUTs the file bytes directly to S3 using that URL
4. S3 ObjectCreated event triggers ImageProcessor for thumbnail generation

**Thumbnail Enrichment**: Each listed file gets a `thumbnailUrl` if a corresponding thumbnail exists in the `thumbnails/` prefix.

**Environment Variables**: `BUCKET_NAME`, `FOLDERS_TABLE`, `FILES_TABLE`, `USERS_PREFIX`, `TRASH_PREFIX`, `THUMBNAIL_PREFIX`, `LOG_LEVEL`

---

### 3. ShareLinkGenerator

- **File**: `backend/lambdas/share_link_generator/handler.py`
- **Route**: `POST /folders/{id}/share`
- **Auth**: Cognito user pool
- **Purpose**: Creates shareable folder links

**Parameters**:
| Parameter | Description |
|---|---|
| `folderId` | The folder to share |
| `expiresInDays` | Link validity (default: 7) |
| `permission` | `view` or `edit` |
| `pin` | Optional 4-6 digit PIN (SHA256 hashed before storage) |
| `sharedWithEmails` | Comma-separated email addresses for "shared with me" queries |

**Behavior**:
- Generates a unique 20-character token
- Hashes the PIN with SHA256 before storing — the raw PIN is never persisted
- Stores `sharedWithEmails` as a comma-separated string to enable "shared with me" queries via `contains` DynamoDB scan
- Updates the folder's `isShared` flag in DynamoDB
- Returns a share URL: `https://{CLOUDFRONT_DOMAIN}/ui/share.html?token={TOKEN}`

**Environment Variables**: `BUCKET_NAME`, `FOLDERS_TABLE`, `SHARES_TABLE`, `CLOUDFRONT_DOMAIN`, `LOG_LEVEL`

---

### 4. PublicAccessHandler

- **File**: `backend/lambdas/public_access_handler/handler.py`
- **Routes**: `GET /share/{token}`, `POST /share/{token}`, `POST /share/{token}/verify`
- **Auth**: None (publicly accessible)
- **Purpose**: Handles anonymous access to shared folders

**Endpoint Details**:

| Method | Path | Description |
|---|---|---|
| `GET` | `/share/{token}` | Return folder contents. If share has `pinHash`, returns `{requiresPin: true}` instead. |
| `POST` | `/share/{token}/verify` | Accepts `{pin: "..."}`, compares SHA256 hash, returns folder contents on match. |
| `POST` | `/share/{token}` | Upload file (only if `permission=edit`), generates presigned URL. |

**Security**:
- Validates the share exists and hasn't expired (checks `expiresAt` timestamp)
- PIN-protected shares require verification before any content is returned
- Uploads on edit shares use presigned URLs scoped to the shared folder's S3 prefix

**Environment Variables**: `BUCKET_NAME`, `FOLDERS_TABLE`, `FILES_TABLE`, `SHARES_TABLE`, `USERS_PREFIX`, `LOG_LEVEL`

---

### 5. ImageProcessor

- **File**: `backend/lambdas/image_processor/handler.py`
- **Trigger**: EventBridge rule firing on S3 `ObjectCreated` events
- **Auth**: None (internally invoked by EventBridge)
- **Purpose**: Auto-generate thumbnails for uploaded images

**Behavior**:
- Triggered when any object is created under the `users/` S3 prefix
- Skips processing for:
  - Non-image files (checks `ContentType` for `image/*`)
  - Objects already inside the `thumbnails/` prefix (avoids infinite loops)
  - Objects in the `trash/` prefix
- Downloads the uploaded image from S3, resizes to 200×200 pixels maintaining aspect ratio
- Stores the thumbnail at `thumbnails/{relative-path}`
- Errors are logged and swallowed (non-fatal — a failed thumbnail does not block the upload)

**Dependencies**: `boto3`, `Pillow`

**Environment Variables**: `BUCKET_NAME`, `USERS_PREFIX`, `THUMBNAIL_PREFIX`, `LOG_LEVEL`

---

### 6. WebDAVHandler

- **File**: `backend/lambdas/webdav_handler/handler.py`
- **Route**: `ANY /webdav/{proxy+}`
- **Auth**: Basic authentication (HTTP Basic header → Cognito `USER_PASSWORD_AUTH` auth flow)
- **Purpose**: WebDAV-compatible endpoint for desktop clients (Cyberduck, Mountain Duck, etc.)

**Operations**:

| Operation | Trigger | Description |
|---|---|---|
| `PROPFIND` | `?method=PROPFIND` or POST `{"action":"propfind"}` | List folder contents as JSON |
| `MKCOL` | `?method=MKCOL` or POST `{"action":"mkcol"}` | Create folder |
| `MOVE` | `?method=MOVE` | Rename or move files/folders |
| `GET` | Standard HTTP GET | Download file (302 redirect to presigned S3 URL) |
| `PUT` | Standard HTTP PUT | Upload file (auto-creates parent folder if missing) |
| `DELETE` | Standard HTTP DELETE | Delete file or folder (hard delete) |
| `OPTIONS` | Standard HTTP OPTIONS | Return DAV capabilities header |

**Limitation**: API Gateway does not natively support `PROPFIND`, `MKCOL`, or `MOVE` as HTTP methods. The handler works around this by accepting these operations via a `?method=` query parameter on a GET request, or via a POST body with an `action` field describing the desired operation.

**Authentication**: Extracts credentials from the HTTP Basic `Authorization` header and authenticates against Cognito using the `USER_PASSWORD_AUTH` flow.

**Environment Variables**: `BUCKET_NAME`, `FOLDERS_TABLE`, `FILES_TABLE`, `USERS_PREFIX`, `THUMBNAIL_PREFIX`, `USER_POOL_ID`, `WEB_CLIENT_ID`, `LOG_LEVEL`

---

## Backend — Shared Utilities

- **Directory**: `backend/shared/`

### `config.py`

A dataclass that reads all environment variables with sensible defaults, providing type-safe configuration to all Lambda functions. Each Lambda function imports the config and destructures the subset of variables it needs.

### `utils.py`

Utility functions shared across all Lambda handlers:

| Function | Description |
|---|---|
| `DecimalEncoder` | JSON encoder that converts DynamoDB `Decimal` types to floats/ints for serialization |
| `response()` | Formats API Gateway response dict with status code, headers (CORS), and body |
| `get_user_from_event()` | Extracts the Cognito username from the API Gateway event context |
| `parse_body()` | Safely parses JSON from the API Gateway event body, returning a dict |
| `generate_file_id()` | Produces a unique file identifier (UUID-based) |
| `format_bytes()` | Converts byte counts to human-readable strings (KB, MB, GB) |

---

## Frontend — Web UI

- **Directory**: `frontend/ui/`

### `index.html`

Single-page application serving all application views. Views are toggled via CSS `display` properties based on authentication state and user navigation:

| View | Description |
|---|---|
| Login / Signup | Authentication forms with email/password |
| Verify | Cognito email verification code entry |
| Forgot Password / Reset Password | Password recovery flow |
| Dashboard | Folder tree listing with create/rename/delete/share controls |
| Folder Files | File grid within a selected folder with upload, drag-and-drop, preview |
| Search | Search results across all user files |
| Trash | Soft-deleted files with restore and permanent delete |
| Admin | Admin-only user management panel (visible only when `isAdmin` flag is set) |
| Account | Account settings and delete account option |
| Shared With Me | Folders others have shared with the current user |

**Modals**: Create folder, rename, move, file preview, share link generation.

### `app.js`

Complete application logic (~1100 lines) handling:

- **Auth flows**: Sign-up, login, email verification, forgot/reset password, sign-out, session token refresh
- **Folder CRUD**: Create, list, delete, rename via FolderManager Lambda
- **File operations**: Upload (single and bulk), list, search, delete, rename, move via UploadHandler Lambda
- **Directory upload**: Walks the directory tree using `webkitGetAsEntry()` / `FileSystemDirectoryEntry` for recursive folder upload
- **Drag-and-drop**: Handles dropped files and directories, preserving folder structure
- **Search and sort**: Search across all files, sort by name/date/size, filter by type
- **File preview**: Opens image preview modal for supported file types
- **Batch operations**: Select multiple files for batch delete or move
- **Share links**: Generates share links with optional PIN and expiration
- **Trash management**: View trashed files, restore, empty trash
- **Admin panel**: List and delete Cognito users (admin only)
- **Theme switching**: Toggles between light and dark themes, persisted in `localStorage`

All API communication uses `fetch()` directly — no AWS SDK is used in the frontend. Authentication tokens are passed in `Authorization` headers.

### `style.css`

Responsive design (~850 lines) featuring:

- **CSS custom properties** for light and dark themes, swapped via a `data-theme` attribute on `<body>`:
  - Light: white backgrounds, dark text, blue accents
  - Dark: dark backgrounds, light text, purple/teal accents
- **Gradient auth pages** with animated backgrounds on login/signup views
- **Card hover effects** with subtle transforms and shadows on folder and file cards
- **Modal animations** with fade-in and slide-down transitions
- **Mobile breakpoints**:
  - 768px: Collapsed sidebar, stacked layout, responsive file grid (2 columns)
  - 400px: Single-column file grid, compact controls, smaller text
- Utility classes for spinner, hidden elements, flex layout, and text truncation

### `share.html`

Standalone public share page linked from share URLs. Contains:

- **PIN entry screen**: Shown when the share is PIN-protected — validates PIN via `POST /share/{token}/verify`
- **File grid**: Displays shared folder contents with download links
- **Upload zone**: Visible only when the share has `permission=edit` — accepts drag-and-drop or click-to-select file uploads
- **Backend communication**: Talks directly to the PublicAccessHandler endpoints (`GET /share/{token}`, `POST /share/{token}/verify`, `POST /share/{token}`)

### Architecture

The frontend is a **pure HTML/CSS/JS** single-page application with no build tools, frameworks, or bundlers. It communicates with:

- **Cognito** directly via `fetch()` for authentication operations (sign-up, login, verify, forgot/reset password, token refresh)
- **API Gateway** for all backend operations (folder/file CRUD, share management, admin functions)
- **S3** directly via presigned URLs for file uploads and downloads

No AWS SDK is loaded — all API calls use plain `fetch()` with JSON request/response bodies.
