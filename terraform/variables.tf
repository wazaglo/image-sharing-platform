variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile"
  type        = string
  default     = "gloria"
}

variable "bucket_name" {
  description = "S3 bucket name for data and UI"
  type        = string
  default     = "nunya-pixel"
}

variable "users_prefix" {
  description = "Prefix for user uploaded files"
  type        = string
  default     = "users/"
}

variable "thumbnail_prefix" {
  description = "Prefix for generated thumbnails"
  type        = string
  default     = "thumbnails/"
}

variable "trash_prefix" {
  description = "Prefix for deleted objects"
  type        = string
  default     = "trash/"
}

variable "log_level" {
  description = "Logging level for Lambda functions"
  type        = string
  default     = "INFO"
}

variable "lambda_memory_size" {
  description = "Memory in MB for Lambda functions"
  type        = number
  default     = 128
}

variable "lambda_timeout" {
  description = "Timeout in seconds for Lambda functions"
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

variable "admin_emails" {
  description = "Comma-separated admin email addresses"
  type        = string
  default     = "dev-admin@imageshare.com"
}

variable "alarm_email" {
  description = "Email address for alarm notifications"
  type        = string
  default     = "admin@example.com"
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN for custom CloudFront domain"
  type        = string
  default     = ""
}
