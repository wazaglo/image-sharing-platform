resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "ImageShare-OAC-${var.environment}"
  description                       = "OAC for ImageShare ${var.environment} S3 origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  comment             = "ImageShare Frontend Distribution - ${var.environment}"
  default_root_object = "/ui/index.html"
  price_class         = "PriceClass_100"
  http_version        = "http2"
  is_ipv6_enabled     = true

  origin {
    domain_name              = "${var.bucket_name}.s3.${var.aws_region}.amazonaws.com"
    origin_id                = "S3Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id
  }

  default_cache_behavior {
    target_origin_id       = "S3Origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    compress               = true
  }

  custom_error_response {
    error_code            = 404
    response_page_path    = "/ui/index.html"
    response_code         = 200
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 403
    response_page_path    = "/ui/index.html"
    response_code         = 200
    error_caching_min_ttl = 0
  }

  aliases = var.certificate_arn != "" ? ["imageshare-${var.environment}.example.com"] : []

  viewer_certificate {
    cloudfront_default_certificate = var.certificate_arn == ""
    acm_certificate_arn            = var.certificate_arn == "" ? null : var.certificate_arn
    ssl_support_method             = var.certificate_arn == "" ? null : "sni-only"
    minimum_protocol_version       = var.certificate_arn == "" ? null : "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = {
    Name        = "ImageShare-Distribution-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

# Remove the generic AllowCloudFrontOACRead from storage bucket policy
# and replace with specific distribution ARN here
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.data.id
  policy = data.aws_iam_policy_document.combined_bucket_policy.json
}

data "aws_iam_policy_document" "combined_bucket_policy" {
  statement {
    sid    = "AllowCloudFrontOACRead"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.bucket_name}/ui/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${aws_cloudfront_distribution.main.id}"]
    }
  }
  statement {
    sid    = "DenyInsecureConnections"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${var.bucket_name}",
      "arn:aws:s3:::${var.bucket_name}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
