resource "aws_s3_bucket" "data" {
  bucket = var.bucket_name
  tags = {
    Name        = "ImageShare-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "AbortIncompleteMultipartUploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  rule {
    id     = "ExpireTrash"
    status = "Enabled"
    filter {
      prefix = var.trash_prefix
    }
    expiration {
      days = 30
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  cors_rule {
    allowed_methods = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    allowed_origins = ["https://${aws_cloudfront_distribution.main.domain_name}"]
    allowed_headers = ["*"]
    expose_headers  = ["ETag", "x-amz-request-id", "x-amz-id-2"]
    max_age_seconds = 3600
  }
}

# Bucket policy is managed in frontend.tf (includes CloudFront OAC + DenyInsecureConnections)

resource "aws_dynamodb_table" "folders" {
  name         = "ImageShare-Folders-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "folderId"
  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "folderId"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
  server_side_encryption {
    enabled = true
  }
  tags = {
    Name        = "ImageShare-Folders-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_dynamodb_table" "files" {
  name         = "ImageShare-Files-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "fileId"
  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "fileId"
    type = "S"
  }
  attribute {
    name = "folderId"
    type = "S"
  }
  global_secondary_index {
    name            = "folderId-index"
    hash_key        = "folderId"
    projection_type = "ALL"
  }
  point_in_time_recovery {
    enabled = true
  }
  server_side_encryption {
    enabled = true
  }
  tags = {
    Name        = "ImageShare-Files-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_dynamodb_table" "shares" {
  name         = "ImageShare-Shares-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "shareToken"
  range_key    = "userId"
  attribute {
    name = "shareToken"
    type = "S"
  }
  attribute {
    name = "userId"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
  server_side_encryption {
    enabled = true
  }
  tags = {
    Name        = "ImageShare-Shares-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}
