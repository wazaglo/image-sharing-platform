# Terraform - ImageShare Infrastructure

Terraform configuration for deploying the ImageShare platform on AWS.

## Structure

```
terraform/
├── provider.tf          # AWS provider + backend config
├── variables.tf         # All input variables
├── outputs.tf           # All output values
├── storage.tf           # S3 bucket + DynamoDB tables
├── auth.tf              # Cognito user pool + clients
├── compute.tf           # IAM + Lambda + EventBridge + SQS
├── api-gateway.tf       # API Gateway REST API + Lambda permissions
├── frontend.tf          # CloudFront distribution + bucket policy
├── monitoring.tf        # CloudWatch dashboard + SNS alarms
├── lambda-zips/         # Built Lambda deployment packages
├── environments/
│   ├── dev/             # Dev environment vars
│   └── prod/            # Prod environment vars
└── README.md
```

## Prerequisites

- Terraform >= 1.5
- AWS CLI configured with profile `gloria`
- Lambda handler code in `src/backend/lambdas/`

## Deployment

```bash
# Dev environment
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform plan -var-file=environments/dev/terraform.tfvars -out plan.tfplan
terraform -chdir=terraform apply plan.tfplan

# Or using the Makefile
make tf-init
make tf-plan env=dev
make tf-apply env=dev
```

## Backend State

State is configured for S3 backend (bucket: `image-share-terraform-state`).
For local testing, use `-backend=false` or override in a `backend.hcl` file.

```bash
terraform -chdir=terraform init -backend-config="bucket=image-share-terraform-state" \
  -backend-config="key=dev/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="encrypt=true"
```
