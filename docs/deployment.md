# Deployment Guide

## 1. Prerequisites

- Python 3.11+
- AWS CLI v2 installed and configured (`aws configure`)
- An AWS account with sufficient permissions
- A domain name (optional, for custom CloudFront URL)

Verify your setup:

```bash
aws sts get-caller-identity
python --version
```

## 2. Clone and Configure

```bash
git clone <repo-url> image-sharing-platform
cd image-sharing-platform
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

## 3. Create Parameter Files

Edit the environment parameter files in `cloudformation/parameters/`:

- `dev.json`. Update `AdminEmails` and `BucketName`
- `prod.json`. Update `AdminEmails` and `BucketName`

The bucket name must be globally unique across all AWS accounts.

## 4. Deploy Storage Stack

This creates S3 buckets and DynamoDB tables.

```bash
aws cloudformation deploy \
  --stack-name image-share-storage-dev \
  --template-file cloudformation/templates/01-storage.yaml \
  --parameter-overrides file://cloudformation/parameters/dev.json \
  --capabilities CAPABILITY_NAMED_IAM
```

## 5. Deploy Auth Stack

This creates the Cognito user pool and app client.

```bash
aws cloudformation deploy \
  --stack-name image-share-auth-dev \
  --template-file cloudformation/templates/02-auth.yaml \
  --parameter-overrides EnvironmentName=dev \
  --capabilities CAPABILITY_NAMED_IAM
```

## 6. Package and Deploy Compute Stack

This creates Lambda functions and EventBridge rules.

```bash
aws cloudformation package \
  --template-file cloudformation/templates/03-compute.yaml \
  --s3-bucket <your-bucket-name> \
  --s3-prefix lambda-packages/dev \
  --output-template-file /tmp/packaged-compute-dev.yaml

aws cloudformation deploy \
  --stack-name image-share-compute-dev \
  --template-file /tmp/packaged-compute-dev.yaml \
  --parameter-overrides file://cloudformation/parameters/dev.json \
  --capabilities CAPABILITY_NAMED_IAM
```

## 7. Deploy API Stack

This creates the API Gateway REST API.

```bash
aws cloudformation deploy \
  --stack-name image-share-api-dev \
  --template-file cloudformation/templates/04-api.yaml \
  --parameter-overrides EnvironmentName=dev \
  --capabilities CAPABILITY_NAMED_IAM
```

## 8. Upload Frontend and Deploy Frontend Stack

```bash
# Get bucket name from storage stack
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name image-share-storage-dev \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text)

# Upload UI files
aws s3 sync src/frontend/ui/ s3://${BUCKET}/ui/ \
  --cache-control "max-age=3600"

# Deploy frontend stack (CloudFront)
aws cloudformation deploy \
  --stack-name image-share-frontend-dev \
  --template-file cloudformation/templates/05-frontend.yaml \
  --parameter-overrides EnvironmentName=dev BucketName=${BUCKET} \
  --capabilities CAPABILITY_NAMED_IAM
```

## 9. Deploy Monitoring Stack

```bash
aws cloudformation deploy \
  --stack-name image-share-monitoring-dev \
  --template-file cloudformation/templates/06-monitoring.yaml \
  --parameter-overrides EnvironmentName=dev \
  --capabilities CAPABILITY_NAMED_IAM
```

## 10. Verification Steps

1. Get the CloudFront URL from the frontend stack outputs
2. Open the URL in a browser, the login page should load
3. Create an account via the signup form
4. Verify your email with the confirmation code
5. Log in and create a folder
6. Upload a file
7. Verify the file appears in the folder
8. Generate a share link and open it in an incognito window
9. Check CloudWatch dashboards for metrics

## 11. Environment Promotion

### Dev → Staging → Prod

1. Update parameter files for each environment (bucket names must be unique)
2. Deploy storage stacks for each environment:
   ```bash
   ENV=staging make deploy-storage
   ENV=prod make deploy-storage
   ```
3. Repeat for remaining stacks:
   ```bash
   for stack in auth compute api frontend monitoring; do
     ENV=prod make deploy-$stack
   done
   ```

### Using the deployment script

```bash
# Deploy to dev
bash cloudformation/scripts/deploy.sh dev us-east-1 default

# Deploy to prod
bash cloudformation/scripts/deploy.sh prod us-east-1 prod-profile
```

## 12. Rollback Procedures

### CloudFormation Stack Failure

If a stack deployment fails:

1. Check the CloudFormation console or AWS CLI for error details
2. Fix the issue (e.g., parameter values, IAM permissions)
3. Run the deploy command again. CloudFormation will update the existing stack

### Full Platform Rollback

To tear down all stacks (in reverse order):

```bash
aws cloudformation delete-stack --stack-name image-share-monitoring-dev
aws cloudformation delete-stack --stack-name image-share-frontend-dev
aws cloudformation delete-stack --stack-name image-share-api-dev
aws cloudformation delete-stack --stack-name image-share-compute-dev
aws cloudformation delete-stack --stack-name image-share-auth-dev
aws cloudformation delete-stack --stack-name image-share-storage-dev
```

Note: S3 buckets must be emptied before the storage stack can be deleted.

### DynamoDB Restore

To restore from a point-in-time backup:

```bash
aws dynamodb restore-table-to-point-in-time \
  --source-table-name image-share-dev-folders \
  --target-table-name image-share-dev-folders-restored \
  --restore-date-time "2026-07-15T00:00:00Z"
```

## 13. Troubleshooting

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| Stack creation fails with "Bucket already exists" | S3 bucket name is taken | Change the BucketName parameter |
| Lambda function not found during deploy | Compute stack not packaged | Run `aws cloudformation package` before deploy |
| API returns 401 Unauthorized | Missing or invalid JWT | Re-authenticate via `POST /auth/login` |
| Upload fails with 403 | Presigned URL expired | Generate a new URL (URLs expire in 5 minutes) |
| Thumbnails not generating | S3 event not triggering | Check EventBridge rule is enabled |
| CloudFront returns 403 | OAC not configured correctly | Verify S3 bucket policy allows CloudFront OAC |
| WebDAV returns 401 | Invalid Basic auth credentials | Verify email and password are correct |
| "Shared with me" shows nothing | No one shared to your email | Ask another user to share a folder with you |
| DynamoDB throttling errors | PAY_PER_REQUEST limits exceeded | Contact AWS Support to increase service quotas |
