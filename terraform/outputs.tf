output "bucket_name" {
  description = "S3 Data Bucket Name"
  value       = aws_s3_bucket.data.id
}

output "bucket_arn" {
  description = "S3 Data Bucket ARN"
  value       = aws_s3_bucket.data.arn
}

output "folders_table_name" {
  description = "Folders DynamoDB Table Name"
  value       = aws_dynamodb_table.folders.name
}

output "files_table_name" {
  description = "Files DynamoDB Table Name"
  value       = aws_dynamodb_table.files.name
}

output "shares_table_name" {
  description = "Shares DynamoDB Table Name"
  value       = aws_dynamodb_table.shares.name
}

output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.main.arn
}

output "web_app_client_id" {
  description = "Web Application Client ID"
  value       = aws_cognito_user_pool_client.web.id
}

output "cli_app_client_id" {
  description = "CLI Application Client ID"
  value       = aws_cognito_user_pool_client.cli.id
}

output "cli_app_client_secret" {
  description = "CLI Application Client Secret"
  value       = aws_cognito_user_pool_client.cli.client_secret
  sensitive   = true
}

output "user_pool_domain" {
  description = "Cognito User Pool Domain"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "api_endpoint" {
  description = "API Gateway Endpoint URL"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
}

output "api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.main.id
}

output "cloudfront_domain_name" {
  description = "CloudFront Distribution Domain Name"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "distribution_id" {
  description = "CloudFront Distribution ID"
  value       = aws_cloudfront_distribution.main.id
}

output "dashboard_name" {
  description = "CloudWatch Dashboard Name"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "alarm_topic_arn" {
  description = "SNS Alarm Topic ARN"
  value       = aws_sns_topic.alarms.arn
}
