# ImageShare — Serverless Image Sharing Platform

![MIT License](https://img.shields.io/badge/license-MIT-blue)
![AWS Serverless](https://img.shields.io/badge/AWS-serverless-orange)

A fully serverless image sharing platform built on AWS, inspired by ownCloud and Nextcloud. ImageShare provides secure file storage, sharing, and management through a modern web UI with a purple-blue gradient theme. The entire backend runs on AWS Lambda, DynamoDB, S3, API Gateway, Cognito, EventBridge, and CloudFront — zero servers to manage.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    CloudFront                         │
│          ┌─────────────────┐  ┌──────────────────┐   │
│          │  S3 (UI Static) │  │  S3 (File Store) │   │
│          │  /ui/           │  │  /users/          │   │
│          │                 │  │  /thumbnails/     │   │
│          └────────┬────────┘  └────────▲─────────┘   │
│                   │                     │             │
│        ┌──────────┴──────────┐          │             │
│        │   API Gateway REST  │          │             │
│        │   /folders/*        │          │             │
│        │   /share/*          │          │             │
│        │   /webdav/*         │          │             │
│        └──────────┬──────────┘          │             │
│                   │                     │             │
│        ┌──────────▼──────────┐          │             │
│        │   Cognito User Pool │          │             │
│        │   (Sign-up / Login) │          │             │
│        └─────────────────────┘          │             │
│                                          │             │
│   ┌──────────────────────────────────────┼──────────┐ │
│   │            Lambda Functions          │          │ │
│   │                                      │          │ │
│   │  FolderManager ────┐                 │          │ │
│   │  UploadHandler ────┤                 │          │ │
│   │  ShareLinkGen  ────┤── DynamoDB      │          │ │
│   │  PublicAccess  ────┘                 │          │ │
│   │  WebDAVHandler                       │          │ │
│   │  ImageProcessor ─── EventBridge ◄────┘          │ │
│   └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

The browser serves static assets from S3 via CloudFront. API calls go through CloudFront to API Gateway, which authorizes via Cognito and routes to Lambda functions. Lambdas coordinate file metadata in DynamoDB and file objects in S3. When a file lands in S3, an EventBridge rule triggers the ImageProcessor Lambda to generate thumbnails. Public share links bypass Cognito and go through a dedicated handler with PIN verification.

---

## Features

- 📧 **Email sign-up/login** — Cognito-powered registration, login, email verification, and password reset
- 📁 **Folder management** — Create, rename, move, delete folders with nested subfolder support and recursive cleanup
- 📤 **File upload** — Single and multi-file upload with drag-and-drop zone, progress bar, and resume
- 📂 **Folder upload** — Upload entire directory trees via `webkitdirectory` attribute
- 🖼️ **File preview** — Inline preview for images, PDFs, text/code files, and video/audio
- 🔍 **Full-text file search** — Search files by name across all folders and subfolders
- 🔀 **Sort / filter** — Sort by name, size, or type; filter by all files, images, video, or PDF
- 🌙 **Dark mode** — Toggle light/dark theme with `localStorage` persistence across sessions
- 🔗 **Shareable folder links** — Generate share links with optional expiry date and view/edit permissions
- 🔒 **PIN-protected shares** — Protect share links with a numeric PIN, hashed via SHA-256
- 👥 **Share with specific users** — Share folders directly with other registered users by email address
- 📋 **Shared with me** — Dedicated view listing all folders shared to your email address
- 🖥️ **WebDAV endpoint** — Full WebDAV protocol support (PROPFIND, MKCOL, MOVE, GET, PUT, DELETE) for desktop clients
- 🗑️ **Trash / recycle bin** — Soft-delete files and folders with restore or permanent empty-trash
- 👤 **Account management** — Change email, update password, delete account from within the UI
- 🔧 **Admin panel** — List all registered users and delete users (admin-only access)
- ✅ **Batch file operations** — Multi-select files for batch delete with confirmation dialog
- 📱 **Responsive design** — Fully responsive UI works on mobile, tablet, and desktop viewports
- 🎨 **Modern theme** — Gradient purple-blue color scheme with smooth transitions and card-based layout
- 📄 **File type icons** — Visual file type indicators for images, PDFs, code, archives, and more
- ⚡ **Presigned URLs** — Direct S3 upload via presigned URLs for fast, scalable file uploads

---

## Prerequisites

- **Python 3.11+** — Runtime for Lambda functions and local testing
- **AWS CLI v2** — Configured with credentials that have permissions for CloudFormation, S3, DynamoDB, Lambda, API Gateway, Cognito, CloudFront, EventBridge, and IAM
- **AWS Account** — An active AWS account with sufficient service quotas
- **Node.js 18+** (optional) — Only needed if you want to build/minify the frontend assets locally
- **Domain name** (optional) — For a custom CloudFront domain and HTTPS certificate

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> image-sharing-platform && cd image-sharing-platform

# 2. Deploy storage resources (S3 buckets and DynamoDB tables)
aws cloudformation deploy \
  --stack-name image-share-storage \
  --template-file cloudformation/templates/01-storage.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# 3. Deploy auth resources (Cognito User Pool and App Client)
aws cloudformation deploy \
  --stack-name image-share-auth \
  --template-file cloudformation/templates/02-auth.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# 4. Deploy compute resources (Lambda functions and EventBridge rules)
aws cloudformation deploy \
  --stack-name image-share-compute \
  --template-file cloudformation/templates/03-compute.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# 5. Deploy API Gateway and WebDAV endpoint
aws cloudformation deploy \
  --stack-name image-share-api \
  --template-file cloudformation/templates/04-api.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# 6. Upload the frontend S3 bucket and deploy CloudFront distribution
aws cloudformation deploy \
  --stack-name image-share-frontend \
  --template-file cloudformation/templates/05-frontend.yaml \
  --capabilities CAPABILITY_NAMED_IAM
aws s3 sync src/frontend/ui/ s3://<your-ui-bucket>/ui/

# 7. Deploy monitoring and alarms
aws cloudformation deploy \
  --stack-name image-share-monitoring \
  --template-file cloudformation/templates/06-monitoring.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# 8. Open the CloudFront URL from the frontend stack outputs
```

> **Tip:** Replace `<repo-url>` and `<your-ui-bucket>` with actual values. The UI bucket name is available in the outputs of the `image-share-frontend` stack.

---

## Environment Variables

The following environment variables are injected into each Lambda function via the CloudFormation template. Most are read from the stack parameters or resource references at deploy time.

| Variable | Used By | Description |
|----------|---------|-------------|
| `BUCKET_NAME` | All Lambdas | S3 bucket name for file object storage |
| `FOLDERS_TABLE` | FolderManager, ShareLinkGenerator, PublicAccessHandler | DynamoDB table name for folder metadata |
| `FILES_TABLE` | FolderManager, UploadHandler, PublicAccessHandler, WebDAVHandler | DynamoDB table name for file metadata |
| `SHARES_TABLE` | FolderManager, ShareLinkGenerator, PublicAccessHandler | DynamoDB table name for share link records |
| `USERS_PREFIX` | All Lambdas | S3 key prefix for user file storage (`users/`) |
| `THUMBNAIL_PREFIX` | All Lambdas | S3 key prefix for generated thumbnails (`thumbnails/`) |
| `CLOUDFRONT_DOMAIN` | FolderManager, ShareLinkGenerator | CloudFront distribution domain for constructing share URLs |
| `LOG_LEVEL` | All Lambdas | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `ADMIN_EMAILS` | FolderManager | Comma-separated list of email addresses granted admin privileges |
| `USER_POOL_ID` | WebDAVHandler | Cognito User Pool ID for WebDAV Basic auth validation |
| `WEB_CLIENT_ID` | WebDAVHandler | Cognito App Client ID used by the WebDAV handler |

---

## Lambda Functions

| Function | Route | Auth | Description |
|----------|-------|------|-------------|
| **FolderManager** | `POST /folders` | Cognito | Handles folder CRUD (create, list, rename, delete), user account management, admin user listing/deletion, and the "shared with me" view |
| **UploadHandler** | `POST /folders/{id}/files` | Cognito | Handles file CRUD (upload, list, rename, move, delete), full-text file search, trash/restore, batch operations, and presigned URL generation |
| **ShareLinkGenerator** | `POST /folders/{id}/share` | Cognito | Creates share links with optional expiry date, view/edit permissions, SHA-256 PIN hashing, and email-based folder sharing |
| **PublicAccessHandler** | `GET/POST /share/{token}` | None (public) | Serves public share pages, verifies PIN codes, lists shared files, and handles file uploads to shared folders |
| **ImageProcessor** | EventBridge trigger (S3 `PutObject`) | — | Listens for new objects in S3, generates resized thumbnail images, and writes them to the thumbnail prefix |
| **WebDAVHandler** | `ANY /webdav/{proxy+}` | Basic Auth | Emulates the WebDAV protocol so desktop clients (Windows Explorer, macOS Finder, Cyberduck) can browse and manage files |

---

## Project Structure

```
image-sharing-platform/
├── .github/
│   └── workflows/              # CI/CD pipeline definitions
├── cloudformation/
│   ├── templates/              # CloudFormation YAML templates (01-06)
│   ├── parameters/             # Dev/prod parameter JSON files
│   └── scripts/                # Deploy and teardown helper scripts
├── docs/
│   ├── architecture.md         # Deep-dive architecture documentation
│   ├── api.md                  # API reference with request/response examples
│   └── security.md             # Security model, IAM roles, encryption
├── scripts/
│   ├── deploy.sh               # Full-stack deployment wrapper
│   ├── teardown.sh             # Stack teardown with cleanup
│   └── seed.py                 # Test data seeder for local dev
├── src/
│   ├── backend/
│   │   └── lambdas/            # Python source for each Lambda function
│   │       ├── folder_manager/
│   │       ├── upload_handler/
│   │       ├── share_link_generator/
│   │       ├── public_access_handler/
│   │       ├── image_processor/
│   │       └── webdav_handler/
│   └── frontend/
│       └── ui/                 # HTML, CSS, JS static assets
│           ├── index.html
│           ├── css/
│           ├── js/
│           └── assets/
└── tests/
    ├── unit/                   # Unit tests per Lambda function
    ├── integration/            # Integration tests against deployed stacks
    └── conftest.py             # Shared pytest fixtures
```

---

## Deployment Order

The platform is deployed as six independent CloudFormation stacks. Each builds on the outputs of the previous stacks.

1. **01-storage.yaml** — S3 buckets for files and UI, DynamoDB tables for folders, files, and shares
2. **02-auth.yaml** — Cognito User Pool, User Pool Client, and domain configuration
3. **03-compute.yaml** — Lambda function roles, function definitions, and EventBridge rules
4. **04-api.yaml** — API Gateway REST API, routes, integrations, and WebDAV endpoint
5. **05-frontend.yaml** — CloudFront distribution, S3 bucket policy, and origin access identity
6. **06-monitoring.yaml** — CloudWatch alarms, dashboard, and log group retention policies

All templates accept a `Stage` parameter (`dev` or `prod`) to control resource naming and sizing.

---

## Configuration

Environment-specific parameter files are located in `cloudformation/parameters/`:

- `dev-parameters.json` — Minimized resources, lower DynamoDB read/write capacity, shorter log retention
- `prod-parameters.json` — Production-sized DynamoDB capacity, longer log retention, additional alarms

Override any parameter at deploy time with `--parameter-overrides`:

```bash
aws cloudformation deploy \
  --stack-name image-share-storage \
  --template-file cloudformation/templates/01-storage.yaml \
  --parameter-overrides Stage=prod DynamoDBReadCapacity=10 DynamoDBWriteCapacity=5 \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
