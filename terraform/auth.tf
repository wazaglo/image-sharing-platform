resource "aws_cognito_user_pool" "main" {
  name = "ImageShareUserPool-${var.environment}"

  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = false
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  email_verification_message = "Your ImageShare verification code is {####}"
  email_verification_subject = "Verify your ImageShare account"

  deletion_protection = var.environment == "prod" ? "ACTIVE" : "INACTIVE"

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  tags = {
    Name        = "ImageShareUserPool-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "imageshare-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "ImageShareWebApp-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  explicit_auth_flows           = ["USER_PASSWORD_AUTH"]
  prevent_user_existence_errors = "ENABLED"

  callback_urls = ["https://imageshare-${var.environment}.cloudfront.net"]
  logout_urls   = ["https://imageshare-${var.environment}.cloudfront.net"]

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["implicit"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  supported_identity_providers = ["COGNITO"]
}

resource "aws_cognito_user_pool_client" "cli" {
  name         = "ImageShareCliApp-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret               = true
  explicit_auth_flows           = ["USER_PASSWORD_AUTH"]
  prevent_user_existence_errors = "ENABLED"

  supported_identity_providers = ["COGNITO"]
}
