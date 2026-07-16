# Changelog

## [1.0.0] - 2026-07-16

### Added
- User authentication (signup, login, verify, forgot password, change password)
- Folder management (create, list, rename, delete with recursive children)
- File management (upload with progress bar, download, rename, move, delete)
- Folder upload via webkitdirectory and drag-and-drop directory tree walk
- File preview (images, PDFs, text, code, video)
- Search files by name across all folders
- Sort and filter files (name, size, type; all/images/video/PDF)
- Dark mode with localStorage persistence
- Shareable folder links with configurable expiry and view/edit permissions
- PIN-protected shares with SHA256 hashing
- Shared with me view showing folders shared to your email
- WebDAV endpoint with Basic authentication (PROPFIND, MKCOL, MOVE, GET, PUT, DELETE)
- Trash / recycle bin with soft delete, restore, and empty trash
- Account management (update email, change password, delete account)
- Admin panel (list users, delete users)
- Batch file operations (multi-select, batch delete)
- Responsive design (desktop, tablet, mobile)
- CloudFront CDN with OAC for static UI serving
- Auto-generated thumbnails for uploaded images via EventBridge-triggered Lambda

### Infrastructure
- 6 CloudFormation stacks: storage, auth, compute, API, frontend, monitoring
- DynamoDB tables with PAY_PER_REQUEST billing and PITR
- Lambda functions with ARM64 Graviton, reserved concurrency, DLQ
- API Gateway with Cognito authorizer and throttling
- CloudWatch dashboards and alarms
- Parameter files for dev/prod environments
