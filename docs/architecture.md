# Architecture

## System Architecture

ImageShare is a fully serverless platform built on AWS. The architecture uses managed services exclusively — no EC2 instances, no container orchestration, no manual server provisioning. Every component scales automatically and incurs cost only when used.

### Component Overview

| Component | Service | Purpose |
|-----------|---------|---------|
| CDN | CloudFront | Edge caching, TLS termination, OAC for S3 origin |
| Static Hosting | S3 | Serves the single-page application UI |
| Auth | Cognito | User pools, JWT issuance and validation |
| API | API Gateway | RESTful API with request throttling and authorizer |
| Compute | Lambda | Business logic, file operations, thumbnail generation |
| Metadata | DynamoDB | Folders, files, shares, user settings tables |
| Object Storage | S3 | Original images and generated thumbnails |
| Async Events | EventBridge | Triggers thumbnail generation on upload |
| Monitoring | CloudWatch | Dashboards, logs, alarms, SNS notifications |

## Data Flow

### File Upload

1. Client obtains JWT from Cognito (USER_PASSWORD_AUTH)
2. Client calls API Gateway `POST /files/upload` with file metadata and presigned URL request
3. Lambda generates a presigned S3 PUT URL and returns it to client
4. Client uploads file directly to S3 using the presigned URL
5. S3 `PutObject` event is sent to EventBridge
6. EventBridge triggers the thumbnail Lambda function
7. Thumbnail Lambda reads the original, generates resized versions, writes them back to S3
8. Client calls `POST /files/confirm` to record the file in DynamoDB

### File Download

1. Client requests `GET /files/{fileId}/download`
2. Lambda verifies the user owns the file or has a valid share
3. Lambda generates a presigned S3 GET URL (with expiry)
4. Client downloads file directly from S3 using the presigned URL

### Share Link Generation

1. Client calls `POST /share` with folderId, permission, expiry, optional PIN
2. Lambda generates a unique share token (UUID), hashes the PIN if provided (SHA256)
3. Lambda writes the share record to DynamoDB Shares table
4. Lambda returns the share URL containing the token

### Share Access

1. Recipient opens the share URL in the browser
2. Client fetches share metadata via `GET /share/{token}`
3. If PIN-protected, client prompts for PIN and sends to `POST /share/{token}/verify`
4. Lambda verifies the SHA256 hash matches
5. Client can now list and download files in the shared folder

### WebDAV

1. Client sends request with Basic auth header (email:password)
2. API Gateway invokes a Lambda authorizer that validates credentials against Cognito
3. WebDAV Lambda handles PROPFIND (list), MKCOL (create folder), MOVE (rename), GET (download), PUT (upload), DELETE (delete)
4. All operations read/write both S3 objects and DynamoDB metadata

### Authentication

1. Client sends signup request to Cognito via `POST /auth/signup`
2. Cognito sends verification code via email
3. Client confirms signup via `POST /auth/confirm`
4. Client authenticates via `POST /auth/login` — Cognito returns ID, access, and refresh tokens
5. Client includes the ID token as a Bearer token in subsequent API requests
6. API Gateway Cognito authorizer validates the JWT and passes user claims to Lambda

### Thumbnail Generation

1. S3 `PutObject` event (for image uploads) is delivered to EventBridge
2. EventBridge rule matches the pattern and invokes the thumbnail Lambda
3. Lambda reads the original image from S3 using Pillow
4. Lambda generates thumbnails at predefined sizes (e.g., 200x200, 400x400)
5. Lambda writes thumbnails to S3 with a `thumbnails/` prefix
6. Lambda updates the file record in DynamoDB with thumbnail availability

## Database Schema

### Folders Table

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| userId | String | Partition Key | Cognito user sub |
| folderId | String | Sort Key | UUID v4 |
| folderName | String | | Display name |
| parentId | String | | Parent folder ID (null for root) |
| createdAt | Number | | Epoch timestamp |
| fileCount | Number | | Count of direct children |
| size | Number | | Total size of files in bytes |
| isShared | Boolean | | Whether folder has active shares |

### Files Table

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| userId | String | Partition Key | Cognito user sub |
| fileId | String | Sort Key | UUID v4 |
| folderId | String | | Parent folder ID |
| fileName | String | | Original file name |
| fileSize | Number | | Size in bytes |
| fileType | String | | MIME type |
| s3Key | String | | S3 object key |
| uploadedAt | Number | | Epoch timestamp |
| isDeleted | Boolean | | Soft delete flag |
| originalS3Key | String | | Original S3 key before deletion |
| deletedAt | Number | | Epoch timestamp of deletion |
| hasThumbnail | Boolean | | Whether thumbnail exists |

**GSI: folderId-index** — Allows querying all files in a folder.

### Shares Table

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| shareToken | String | Partition Key | UUID v4 |
| userId | String | Sort Key | Owner's Cognito sub |
| folderId | String | | Shared folder ID |
| permission | String | | "view" or "edit" |
| createdAt | Number | | Epoch timestamp |
| expiresAt | Number | | Expiry epoch (0 = never) |
| isActive | Boolean | | Whether share is active |
| pinHash | String | | SHA256 of PIN (null if no PIN) |
| sharedWithEmails | List of String | | Emails of recipients (for "shared with me") |

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /auth/signup | None | Create account |
| POST | /auth/confirm | None | Confirm verification code |
| POST | /auth/login | None | Authenticate and get tokens |
| POST | /auth/reset-password | None | Request password reset |
| POST | /auth/change-password | JWT | Change password |
| GET | /folders | JWT | List user folders |
| POST | /folders | JWT | Create folder |
| PATCH | /folders/{folderId} | JWT | Rename folder |
| DELETE | /folders/{folderId} | JWT | Delete folder (recursive) |
| GET | /folders/{folderId}/files | JWT | List files in folder |
| GET | /files/{fileId} | JWT | Get file metadata |
| PATCH | /files/{fileId} | JWT | Rename/move file |
| DELETE | /files/{fileId} | JWT | Delete file |
| POST | /files/upload | JWT | Request upload presigned URL |
| POST | /files/confirm | JWT | Confirm upload, record metadata |
| GET | /files/{fileId}/download | JWT/Share | Get download presigned URL |
| GET | /search?q= | JWT | Search files by name |
| GET | /recent | JWT | List recently uploaded files |
| POST | /share | JWT | Create share link |
| GET | /share/{token} | None | Get share metadata |
| POST | /share/{token}/verify | None | Verify PIN |
| GET | /shared-with-me | JWT | List folders shared to user |
| DELETE | /share/{shareToken} | JWT | Revoke share link |
| GET | /trash | JWT | List deleted files |
| POST | /trash/{fileId}/restore | JWT | Restore deleted file |
| DELETE | /trash | JWT | Empty trash |
| GET | /account | JWT | Get user account info |
| PATCH | /account | JWT | Update account (email, etc.) |
| DELETE | /account | JWT | Delete account |
| GET | /admin/users | JWT+Admin | List all users |
| DELETE | /admin/users/{userId} | JWT+Admin | Delete user |
| ALL | /webdav/* | Basic | WebDAV operations |

## Security Architecture

### IAM Roles

- Each Lambda function has a dedicated IAM role with least-privilege permissions
- Lambda roles can only access specific DynamoDB tables and S3 buckets
- API Gateway has permissions to invoke Lambda functions and use Cognito authorizer

### Cognito JWTs

- API Gateway uses a Cognito authorizer to validate JWT tokens
- Lambda receives user claims (sub, email) in the event context
- ID tokens expire after 1 hour; refresh tokens can obtain new ID tokens

### S3 Bucket Policies

- The UI bucket has an OAC policy allowing only CloudFront access
- The objects bucket allows read/write only from Lambda execution roles and presigned URLs
- Direct public access is blocked via `BlockPublicAccess` settings

### CloudFront OAC

- Origin Access Control ensures CloudFront is the only entity that can directly access the S3 UI bucket
- OAC replaces the legacy Origin Access Identity (OAI)
- No public S3 URL exposure for the frontend

### CORS

- API Gateway CORS is configured to allow requests from the CloudFront domain
- Allowed methods: GET, POST, PATCH, DELETE, OPTIONS
- Allowed headers: Content-Type, Authorization, X-Requested-With

## Cost Analysis

Estimated monthly costs for the serverless platform at different usage levels:

| Usage Level | Active Users | Monthly Cost |
|-------------|-------------|--------------|
| Light | 10 | ~$15 |
| Medium | 100 | ~$80 |
| Heavy | 1,000 | ~$400 |

Cost drivers:
- API Gateway: $3.50 per million requests
- Lambda: $0.20 per million requests (128 MB)
- DynamoDB: PAY_PER_REQUEST ($1.25 per million writes, $0.25 per million reads)
- S3: $0.023 per GB for storage
- CloudFront: $0.085 per GB data transfer out
- CloudWatch: $0.30 per GB for logs

## Scalability

- **Lambda**: Scales horizontally with concurrency. Reserved concurrency prevents runaway scaling. Each function handles one request at a time.
- **DynamoDB**: PAY_PER_REQUEST mode handles any throughput automatically. PITR is enabled for point-in-time recovery.
- **S3**: Virtually unlimited storage. Presigned URLs shift transfer burden to clients.
- **API Gateway**: Regional endpoint with throttling (10,000 requests per second by default).
- **CloudFront**: Global edge network with thousands of PoPs.

## Disaster Recovery and Backup

- **DynamoDB PITR**: Continuous backups with 35-day recovery window. Can restore to any point in the last 35 days.
- **S3 Versioning**: Enabled on objects bucket. Allows recovery from accidental overwrites or deletions.
- **S3 Cross-Region Replication**: Optional — can replicate to a secondary region for DR.
- **CloudFormation**: Infrastructure as Code — entire platform can be recreated from templates.
- **Backup Strategy**: Weekly exports of DynamoDB to S3 via AWS Backup, retained for 90 days.
