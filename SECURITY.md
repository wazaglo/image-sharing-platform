# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it by emailing security@example.com. 
Do NOT create a public GitHub issue for security vulnerabilities.

You should receive a response within 48 hours. If you don't, please follow up.
We will keep you informed of the progress toward a fix.

## Security Architecture

### Authentication
- All API requests (except public shares and WebDAV) require a valid Cognito JWT
- JWT tokens expire after 1 hour; refresh tokens are used for renewal
- WebDAV uses Basic authentication with Cognito USER_PASSWORD_AUTH
- PIN codes on shares are hashed with SHA256 before storage

### Authorization
- IAM roles follow least-privilege principle
- Each Lambda function only has access to the resources it needs
- CloudFront Origin Access Control (OAC) restricts S3 access to CloudFront only
- API Gateway acts as the sole entry point for all backend operations

### Data Protection
- S3 bucket encryption: AES-256 (SSE-S3)
- DynamoDB encryption: AWS-owned key at rest
- All data in transit: TLS 1.2+ (HTTPS only)
- CloudFront enforces HTTPS redirect
- S3 bucket policy denies non-HTTPS requests

### Input Validation
- API Gateway validates request structure
- Lambda handlers validate required fields
- File names are escaped for HTML injection prevention (XSS)
- All user input is treated as untrusted

### Secrets Management
- Cognito app client secrets are stored in CloudFormation
- No hardcoded credentials in source code
- AWS CLI profiles are not committed to the repository
- GitHub Actions uses repository secrets for AWS credentials

### Monitoring
- CloudWatch Logs capture all Lambda invocations
- CloudWatch Alarms alert on error rate thresholds
- SNS notifications for operational issues
- Access logging on API Gateway stage

## Data Retention
- Trash items are automatically deleted after 30 days (S3 lifecycle rule)
- CloudWatch logs retained for 14 days (dev) / 30 days (prod)
- DynamoDB Point-in-Time Recovery enables 35-day rollback

## Incident Response
1. Alarm triggers via SNS/email
2. Engineer reviews CloudWatch logs and metrics
3. If data loss: restore from DynamoDB PITR or S3 versioning
4. If security breach: rotate credentials, review access logs
5. Post-mortem and remediation documented
