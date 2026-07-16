# API Reference

Base URL: `https://<api-id>.execute-api.<region>.amazonaws.com/<stage>`

Authentication: Bearer JWT token (obtained from Cognito) for authenticated endpoints.

## Authentication

### POST /auth/signup

Create a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "Str0ng!Passw0rd"
}
```

**Response (200):**
```json
{
  "message": "User created successfully. Verification code sent to email.",
  "cognitoSub": "a1b2c3d4-..."
}
```

### POST /auth/confirm

Confirm account with verification code.

**Request:**
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "message": "Account confirmed successfully."
}
```

### POST /auth/login

Authenticate and receive tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "Str0ng!Passw0rd"
}
```

**Response (200):**
```json
{
  "idToken": "eyJ...",
  "accessToken": "eyJ...",
  "refreshToken": "eyJ...",
  "expiresIn": 3600
}
```

### POST /auth/reset-password

Request a password reset code.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "Password reset code sent to email."
}
```

### POST /auth/change-password

Change password (authenticated).

**Request:**
```json
{
  "previousPassword": "OldPass1!",
  "proposedPassword": "NewPass2@"
}
```

**Response (200):**
```json
{
  "message": "Password changed successfully."
}
```

## Folders

### GET /folders

List all folders for the authenticated user.

**Response (200):**
```json
{
  "folders": [
    {
      "folderId": "uuid",
      "folderName": "My Photos",
      "parentId": null,
      "createdAt": 1700000000,
      "fileCount": 5,
      "size": 1024000,
      "isShared": false
    }
  ]
}
```

### POST /folders

Create a new folder.

**Request:**
```json
{
  "folderName": "Vacation 2026",
  "parentId": null
}
```

**Response (201):**
```json
{
  "folderId": "uuid",
  "folderName": "Vacation 2026",
  "parentId": null,
  "createdAt": 1700000000,
  "fileCount": 0,
  "size": 0,
  "isShared": false
}
```

### PATCH /folders/{folderId}

Rename or move a folder.

**Request:**
```json
{
  "folderName": "Vacation 2026 - Edited",
  "parentId": null
}
```

**Response (200):**
```json
{
  "message": "Folder updated successfully."
}
```

### DELETE /folders/{folderId}

Delete a folder and all its contents (recursive).

**Response (200):**
```json
{
  "message": "Folder and 15 files deleted."
}
```

## Files

### GET /folders/{folderId}/files

List files in a folder.

**Response (200):**
```json
{
  "files": [
    {
      "fileId": "uuid",
      "folderId": "uuid",
      "fileName": "sunset.jpg",
      "fileSize": 2048000,
      "fileType": "image/jpeg",
      "uploadedAt": 1700000000,
      "hasThumbnail": true
    }
  ]
}
```

### GET /files/{fileId}

Get file metadata.

**Response (200):**
```json
{
  "fileId": "uuid",
  "folderId": "uuid",
  "fileName": "sunset.jpg",
  "fileSize": 2048000,
  "fileType": "image/jpeg",
  "s3Key": "uploads/uuid/sunset.jpg",
  "uploadedAt": 1700000000,
  "hasThumbnail": true
}
```

### POST /files/upload

Request a presigned URL for uploading a file.

**Request:**
```json
{
  "folderId": "uuid",
  "fileName": "sunset.jpg",
  "fileSize": 2048000,
  "fileType": "image/jpeg"
}
```

**Response (200):**
```json
{
  "uploadUrl": "https://s3.amazonaws.com/...",
  "uploadHeaders": {
    "content-type": "image/jpeg"
  },
  "fileId": "uuid",
  "s3Key": "uploads/uuid/sunset.jpg"
}
```

### POST /files/confirm

Confirm that a file has been uploaded.

**Request:**
```json
{
  "fileId": "uuid",
  "folderId": "uuid",
  "fileName": "sunset.jpg",
  "fileSize": 2048000,
  "fileType": "image/jpeg",
  "s3Key": "uploads/uuid/sunset.jpg"
}
```

**Response (201):**
```json
{
  "fileId": "uuid",
  "message": "File recorded successfully."
}
```

### GET /files/{fileId}/download

Get a presigned URL for downloading a file.

**Response (200):**
```json
{
  "downloadUrl": "https://s3.amazonaws.com/...",
  "fileName": "sunset.jpg",
  "fileSize": 2048000,
  "expiresIn": 300
}
```

### PATCH /files/{fileId}

Rename or move a file.

**Request:**
```json
{
  "fileName": "sunset-v2.jpg",
  "folderId": "new-folder-uuid"
}
```

**Response (200):**
```json
{
  "message": "File updated successfully."
}
```

### DELETE /files/{fileId}

Soft-delete a file (moves to trash).

**Response (200):**
```json
{
  "message": "File moved to trash."
}
```

## Search

### GET /search?q=keyword&folderId=optional

Search files by name.

**Response (200):**
```json
{
  "results": [
    {
      "fileId": "uuid",
      "fileName": "sunset.jpg",
      "folderId": "uuid",
      "folderName": "Vacation",
      "fileType": "image/jpeg",
      "fileSize": 2048000
    }
  ]
}
```

## Shares

### POST /share

Create a share link for a folder.

**Request:**
```json
{
  "folderId": "uuid",
  "permission": "view",
  "expiresAt": 1700100000,
  "pin": "1234",
  "sharedWithEmails": ["friend@example.com"]
}
```

**Response (201):**
```json
{
  "shareToken": "uuid",
  "shareUrl": "https://<domain>/share/uuid",
  "expiresAt": 1700100000,
  "hasPin": true
}
```

### GET /share/{token}

Get share metadata (public).

**Response (200):**
```json
{
  "folderId": "uuid",
  "folderName": "Shared Folder",
  "permission": "view",
  "hasPin": true,
  "expiresAt": 1700100000
}
```

### POST /share/{token}/verify

Verify a share PIN (public).

**Request:**
```json
{
  "pin": "1234"
}
```

**Response (200):**
```json
{
  "verified": true,
  "folderId": "uuid",
  "folderName": "Shared Folder",
  "permission": "view"
}
```

### GET /shared-with-me

List folders shared to the authenticated user's email.

**Response (200):**
```json
{
  "shares": [
    {
      "shareToken": "uuid",
      "folderId": "uuid",
      "folderName": "Vacation Photos",
      "ownerEmail": "owner@example.com",
      "permission": "view",
      "expiresAt": 1700100000
    }
  ]
}
```

### DELETE /share/{shareToken}

Revoke a share link.

**Response (200):**
```json
{
  "message": "Share link revoked."
}
```

## Trash

### GET /trash

List deleted files.

**Response (200):**
```json
{
  "files": [
    {
      "fileId": "uuid",
      "fileName": "sunset.jpg",
      "fileSize": 2048000,
      "deletedAt": 1700000000
    }
  ]
}
```

### POST /trash/{fileId}/restore

Restore a file from trash.

**Response (200):**
```json
{
  "message": "File restored successfully."
}
```

### DELETE /trash

Permanently delete all trashed files (empty trash).

**Response (200):**
```json
{
  "message": "15 files permanently deleted."
}
```

## Account

### GET /account

Get current user account information.

**Response (200):**
```json
{
  "email": "user@example.com",
  "cognitoSub": "a1b2c3d4-...",
  "createdAt": 1700000000,
  "storageUsed": 10485760,
  "fileCount": 42
}
```

### PATCH /account

Update account details.

**Request:**
```json
{
  "email": "newemail@example.com"
}
```

**Response (200):**
```json
{
  "message": "Account updated. Verification email sent to new address."
}
```

### DELETE /account

Delete the current user's account and all data.

**Response (200):**
```json
{
  "message": "Account and all data deleted."
}
```

## Admin

### GET /admin/users

List all users (admin only).

**Response (200):**
```json
{
  "users": [
    {
      "userId": "uuid",
      "email": "user@example.com",
      "createdAt": 1700000000,
      "fileCount": 42,
      "storageUsed": 10485760
    }
  ]
}
```

### DELETE /admin/users/{userId}

Delete a user and their data (admin only).

**Response (200):**
```json
{
  "message": "User and all data deleted."
}
```

## WebDAV

Endpoint: `https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/webdav`

Authentication: Basic (email:password)

### PROPFIND

List folder contents. Depth: 0 (self), 1 (children).

**Request:**
```
PROPFIND /webdav/{folderId} HTTP/1.1
Depth: 1
```

**Response (207):**
```xml
<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:">
  <response>
    <href>/webdav/{folderId}/</href>
    <propstat>
      <prop>
        <displayname>Folder Name</displayname>
        <getcontentlength>0</getcontentlength>
        <resourcetype><collection/></resourcetype>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>
```

### MKCOL

Create a subfolder.

**Request:**
```
MKCOL /webdav/{parentFolderId}/new-folder HTTP/1.1
```

**Response (201)**

### GET

Download a file.

**Request:**
```
GET /webdav/{folderId}/{fileName} HTTP/1.1
```

**Response (200)** with file body.

### PUT

Upload a file.

**Request:**
```
PUT /webdav/{folderId}/{fileName} HTTP/1.1
Content-Length: 2048000
Content-Type: image/jpeg

<binary data>
```

**Response (201)**

### DELETE

Delete a file or empty folder.

**Request:**
```
DELETE /webdav/{folderId}/{fileName} HTTP/1.1
```

**Response (204)**

### MOVE

Rename or move a file/folder.

**Request:**
```
MOVE /webdav/{sourceFolderId}/{fileName} HTTP/1.1
Destination: /webdav/{destFolderId}/{newFileName}
```

**Response (204)**

## Error Responses

All endpoints return standard error responses:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error description",
  "statusCode": 400
}
```

| Status | Description |
|--------|-------------|
| 400 | Bad request (invalid input, missing fields) |
| 401 | Unauthorized (missing or invalid JWT) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (duplicate folder name, etc.) |
| 429 | Too many requests (throttled) |
| 500 | Internal server error |
