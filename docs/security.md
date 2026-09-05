# Security Documentation

## Authentication Flow

ImageShare uses Amazon Cognito for user authentication with the `USER_PASSWORD_AUTH` flow:

1. User signs up via `POST /auth/signup`. Cognito creates the user in `EXTERNAL_PROVIDER` (email) or `USER_PASSWORD` mode
2. Cognito sends a verification code via email
3. User confirms via `POST /auth/confirm` with the code
4. User authenticates via `POST /auth/login`. Cognito returns three JWTs:
   - **ID Token**: Contains user claims (sub, email). Used as Bearer token for API calls.
   - **Access Token**: Used for Cognito API operations (optional).
   - **Refresh Token**: Long-lived token to obtain new ID/Access tokens.
5. ID tokens expire after 1 hour. The client should use the refresh token before expiry.
6. API Gateway validates the ID token via a Cognito authorizer before forwarding to Lambda.

### Password Policy

- Minimum 8 characters
- Require at least 1 uppercase letter
- Require at least 1 number
- Require at least 1 special character
- Password history: prevents reuse of last 5 passwords

## Authorization

Two authorization layers are used:

### API Gateway Cognito Authorizer

- Validates JWT signatures using Cognito's public JWKs
- Checks token expiry (`exp` claim)
- Extracts user claims (`sub`, `email`, `cognito:groups`)
- Passes claims to Lambda in `event.requestContext.authorizer.claims`

### Lambda-Level Authorization

- Admin endpoints check `cognito:groups` claim for admin group membership
- Resource ownership is verified: users can only access their own folders and files
- Share access is granted only for valid, non-expired share tokens with correct PIN

## Data Encryption

### At Rest

| Layer | Encryption Method |
|-------|------------------|
| S3 Objects | SSE-S3 (AES-256) — enabled by default on all buckets |
| DynamoDB | AWS-managed KMS keys — encryption at rest enabled by default on all tables |
| CloudWatch Logs | AWS-managed KMS keys — enabled by default |
| CloudFront | Not applicable (edge cache holds encrypted data) |

### In Transit

- All API traffic uses TLS 1.2+
- CloudFront enforces HTTPS-only access with redirect from HTTP
- Client-to-CloudFront and CloudFront-to-S3 both use HTTPS
- Cognito endpoints use TLS 1.2+
- S3 presigned URLs use HTTPS

## Input Validation and Sanitization

All API inputs are validated and sanitized:

- **JSON Schema Validation**: API Gateway request body validation
- **Size Limits**: File names limited to 255 characters, folder names to 128 characters, descriptions to 2000 characters
- **Type Checking**: All inputs are typed (string, number, boolean, array)
- **Path Traversal Prevention**: `../` sequences are stripped from paths and file names
- **XSS Prevention**: All user-generated content is HTML-escaped before rendering in the frontend
- **MIME Type Validation**: Upload content types are validated against magic bytes (server-side)

## PIN Hashing

Share link PINs are handled securely:

1. PIN is sent to `POST /share` endpoint over HTTPS
2. Lambda hashes the PIN using SHA-256 before storing in DynamoDB
3. PIN is never stored in plaintext
4. Verification via `POST /share/{token}/verify` compares SHA-256 hashes
5. Rate limiting on PIN verification attempts (5 attempts per minute per IP)

## CloudFront Origin Access Control (OAC)

CloudFront is configured with OAC to secure access to the S3 UI bucket:

1. An OAC is created in CloudFront and associated with the S3 origin
2. The S3 bucket policy allows `s3:GetObject` only when the principal is the CloudFront OAC
3. Direct S3 URL access (bypassing CloudFront) returns 403 Forbidden
4. OAC replaces the legacy Origin Access Identity (OAI) and provides stronger security guarantees

### S3 Bucket Policy for OAC

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::bucket-name/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::account-id:distribution/distribution-id"
        }
      }
    }
  ]
}
```

## CORS Configuration

API Gateway CORS is configured to restrict cross-origin requests:

- **AllowedOrigin**: The CloudFront distribution domain (e.g., `https://d123.cloudfront.net`)
- **AllowedMethods**: GET, POST, PATCH, DELETE, OPTIONS
- **AllowedHeaders**: Content-Type, Authorization, X-Requested-With
- **ExposeHeaders**: ETag, x-amz-request-id
- **MaxAge**: 86400 seconds (24 hours)

## IAM Least Privilege

Every IAM role follows least privilege:

- **Lambda Execution Roles**: Only permit actions on specific resources:
  - `dynamodb:GetItem`, `Query`, `PutItem`, `UpdateItem`, `DeleteItem` on `arn:aws:dynamodb:*:*:table/image-share-*`
  - `s3:GetObject`, `PutObject`, `DeleteObject` on `arn:aws:s3:::bucket-name/uploads/*`
  - `s3:PutObject` on `arn:aws:s3:::bucket-name/thumbnails/*`
  - No wildcard permissions on any resource

- **API Gateway Role**: Only `lambda:InvokeFunction` on specific Lambda functions

- **CloudFormation Service Role**: Limited to creating/modifying the specific resources in the template

No roles have `iam:PassRole` to unauthorized services. No roles have `*` on `Action` or `Resource`.

## Secrets Management

- Cognito app client secrets are stored securely by AWS
- No secrets are hardcoded in Lambda code
- Environment variables (e.g., table names, bucket names) are passed via CloudFormation
- No database connection strings (DynamoDB is accessed via IAM)
- If custom domain with SSL is used, the ACM certificate is referenced by ARN, not embedded

## Audit Logging

All operations are logged to CloudWatch Logs:

- **Authentication Events**: Signup, login, failed login attempts, password changes
- **API Operations**: All CRUD operations on folders, files, shares
- **Admin Actions**: User listing, user deletion
- **Errors**: All Lambda errors, API Gateway 4xx/5xx responses

Log groups use encryption at rest with AWS-managed KMS keys. Log retention is configurable (14 days for dev, 30 days for prod).

### Audit Log Schema

```
{
  "timestamp": "2026-07-16T12:00:00Z",
  "userId": "a1b2c3d4-...",
  "action": "FILE_UPLOAD",
  "resource": "file/uuid",
  "status": "SUCCESS",
  "ipAddress": "203.0.113.1",
  "userAgent": "Mozilla/5.0...",
  "details": {
    "fileName": "sunset.jpg",
    "fileSize": 2048000
  }
}
```

## Incident Response

In case of a security incident:

1. **Identification**: CloudWatch alarms trigger SNS notifications for:
   - Spike in 4xx/5xx errors
   - Unusual authentication failures
   - Unexpected data transfer patterns

2. **Containment**:
   - Revoke compromised user tokens via Cognito admin API
   - Disable compromised users in Cognito
   - Block IP addresses via WAF (if configured)
   - If S3 is compromised, enable `BlockPublicAccess` on all buckets

3. **Eradication**:
   - Rotate all IAM credentials
   - Review and update IAM policies
   - Audit DynamoDB and S3 for unauthorized changes

4. **Recovery**:
   - Restore DynamoDB tables from PITR if data is corrupted
   - Restore S3 objects from version history
   - Redeploy CloudFormation stacks from source control

5. **Post-Mortem**:
   - Analyze CloudWatch Logs for root cause
   - Update IAM policies to prevent recurrence
   - Update incident response runbook
   - Notify affected users if necessary

### Security Contacts

Report security vulnerabilities to security@image-share-platform.com. We aim to acknowledge within 24 hours and provide a fix within 7 days.
