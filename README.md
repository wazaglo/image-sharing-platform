# ImageShare — Serverless Image Sharing Platform

![MIT License](https://img.shields.io/badge/license-MIT-blue)
![AWS Serverless](https://img.shields.io/badge/AWS-serverless-orange)

A fully serverless image sharing platform built on AWS, inspired by ownCloud and Nextcloud. ImageShare provides secure file storage, sharing, and management through a modern web UI with a purple-blue gradient theme. The entire backend runs on AWS Lambda, DynamoDB, S3, API Gateway, Cognito, EventBridge, and CloudFront — zero servers to manage.

---

## Architecture

![ImageShare architecture](Image%20Share.png)

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
- **Terraform >= 1.5** — Infrastructure as Code tool for deploying all AWS resources
- **AWS CLI v2** — Configured with credentials  that have permissions for S3, DynamoDB, Lambda, API Gateway, Cognito, CloudFront, EventBridge, and IAM
- **AWS Account** — An active AWS account with sufficient service quotas
- **Node.js 18+** (optional) — Only needed if you want to build/minify the frontend assets locally
- **Domain name** (optional) — For a custom CloudFront domain and HTTPS certificate

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> image-sharing-platform && cd image-sharing-platform

# 2. Initialize Terraform
terraform -chdir=terraform init -backend=false

# 3. Deploy all AWS infrastructure (S3, DynamoDB, Cognito, Lambda, API Gateway, CloudFront)
terraform -chdir=terraform plan -var-file=environments/dev/terraform.tfvars -out plan.tfplan
terraform -chdir=terraform apply plan.tfplan

# 4. Upload the frontend static assets to the UI S3 bucket
aws s3 sync src/frontend/ui/ s3://<your-ui-bucket>/ui/ --cache-control 'max-age=3600'

# 5. Open the CloudFront URL from the Terraform outputs
```

> **Tip:** Replace `<repo-url>` and `<your-ui-bucket>` with actual values. Use `make tf-apply env=dev` as a shortcut for steps 2–3.

---

## Environment Variables

The following environment variables are injected into each Lambda function via the Terraform configuration. Most are read from the input variables or resource references at deploy time.

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
├── terraform/
│   ├── provider.tf             # AWS provider + backend config
│   ├── variables.tf            # All input variables
│   ├── outputs.tf              # All output values
│   ├── storage.tf              # S3 buckets + DynamoDB tables
│   ├── auth.tf                 # Cognito user pool + clients
│   ├── compute.tf              # IAM + Lambda + EventBridge + SQS
│   ├── api-gateway.tf          # API Gateway REST API
│   ├── frontend.tf             # CloudFront + bucket policy
│   ├── monitoring.tf           # CloudWatch dashboard + SNS alarms
│   └── environments/           # Dev/prod var files
│       ├── dev/
│       └── prod/
├── docs/
│   ├── architecture.md         # Deep-dive architecture documentation
│   ├── api.md                  # API reference with request/response examples
│   └── security.md             # Security model, IAM roles, encryption
├── Makefile                    # Convenience targets (tf-*, lint, test)
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

The platform is deployed as a single Terraform configuration composed of multiple resource files. Each file manages a logical layer of the infrastructure.

1. **storage.tf** — S3 buckets for files and UI, DynamoDB tables for folders, files, and shares
2. **auth.tf** — Cognito User Pool, User Pool Client, and domain configuration
3. **compute.tf** — Lambda function roles, function definitions, and EventBridge rules
4. **api-gateway.tf** — API Gateway REST API, routes, integrations, and WebDAV endpoint
5. **frontend.tf** — CloudFront distribution, S3 bucket policy, and origin access identity
6. **monitoring.tf** — CloudWatch alarms, dashboard, and log group retention policies

All configurations accept an `environment` variable (`dev` or `prod`) to control resource naming and sizing.

---

## Configuration

Environment-specific variable files are located in `terraform/environments/`:

- `dev/terraform.tfvars` — Minimized resources, lower DynamoDB read/write capacity, shorter log retention
- `prod/terraform.tfvars` — Production-sized DynamoDB capacity, longer log retention, additional alarms

Override any variable at deploy time with `-var` or a custom `.tfvars` file:

```bash
terraform -chdir=terraform plan \
  -var="environment=prod" \
  -var="bucket_name=my-bucket" \
  -var-file=environments/prod/terraform.tfvars \
  -out plan.tfplan
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
