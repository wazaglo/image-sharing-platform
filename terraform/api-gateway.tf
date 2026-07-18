resource "aws_api_gateway_rest_api" "main" {
  name        = "ImageShareAPI-${var.environment}"
  description = "ImageShare API Gateway - ${var.environment}"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
  minimum_compression_size = 1024
  tags = {
    Name        = "ImageShareAPI-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "ImageShare-CognitoAuthorizer-${var.environment}"
  type            = "COGNITO_USER_POOLS"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  identity_source = "method.request.header.Authorization"
  provider_arns   = [aws_cognito_user_pool.main.arn]
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/api-gateway/ImageShareAPI-${var.environment}"
  retention_in_days = 14
}

locals {
  lambda_invoke_arn = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/"
  cors_headers      = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  cors_methods      = "'GET,POST,PUT,DELETE,OPTIONS'"
}

# ──────────────────────────────────────────────
# Resources
# ──────────────────────────────────────────────

resource "aws_api_gateway_resource" "folders" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "folders"
}

resource "aws_api_gateway_resource" "folders_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.folders.id
  path_part   = "{id}"
}

resource "aws_api_gateway_resource" "folders_id_files" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.folders_id.id
  path_part   = "files"
}

resource "aws_api_gateway_resource" "folders_id_share" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.folders_id.id
  path_part   = "share"
}

resource "aws_api_gateway_resource" "share" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "share"
}

resource "aws_api_gateway_resource" "share_token" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.share.id
  path_part   = "{token}"
}

resource "aws_api_gateway_resource" "share_token_verify" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.share_token.id
  path_part   = "verify"
}

resource "aws_api_gateway_resource" "webdav" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "webdav"
}

resource "aws_api_gateway_resource" "webdav_proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.webdav.id
  path_part   = "{proxy+}"
}

# ──────────────────────────────────────────────
# Methods - OPTIONS (CORS) shared template
# ──────────────────────────────────────────────

locals {
  options_method_response_params = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  options_integration_response_params = {
    "method.response.header.Access-Control-Allow-Headers" = local.cors_headers
    "method.response.header.Access-Control-Allow-Methods" = local.cors_methods
    "method.response.header.Access-Control-Allow-Origin"  = "'https://${aws_cloudfront_distribution.main.domain_name}'"
  }
}

resource "aws_api_gateway_method" "folders_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.folders.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "folders_options_200" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.folders.id
  http_method         = aws_api_gateway_method.folders_options.http_method
  status_code         = "200"
  response_parameters = local.options_method_response_params
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "folders_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.folders.id
  http_method = aws_api_gateway_method.folders_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "folders_options" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.folders.id
  http_method         = aws_api_gateway_method.folders_options.http_method
  status_code         = aws_api_gateway_method_response.folders_options_200.status_code
  response_parameters = local.options_integration_response_params
  response_templates = {
    "application/json" = ""
  }
}

# ──────────────────────────────────────────────
# Methods - POST /folders
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "folders_post" {
  rest_api_id          = aws_api_gateway_rest_api.main.id
  resource_id          = aws_api_gateway_resource.folders.id
  http_method          = "POST"
  authorization        = "COGNITO_USER_POOLS"
  authorizer_id        = aws_api_gateway_authorizer.cognito.id
  authorization_scopes = ["email", "openid"]
}

resource "aws_api_gateway_integration" "folders_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.folders.id
  http_method             = aws_api_gateway_method.folders_post.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.folder_manager.arn}/invocations"
}

resource "aws_api_gateway_method_response" "folders_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.folders.id
  http_method = aws_api_gateway_method.folders_post.http_method
  status_code = "200"
}

# ──────────────────────────────────────────────
# Methods - OPTIONS /folders/{id}/files
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "folders_id_files_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.folders_id_files.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "folders_id_files_options_200" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.folders_id_files.id
  http_method         = aws_api_gateway_method.folders_id_files_options.http_method
  status_code         = "200"
  response_parameters = local.options_method_response_params
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "folders_id_files_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.folders_id_files.id
  http_method = aws_api_gateway_method.folders_id_files_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "folders_id_files_options" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.folders_id_files.id
  http_method         = aws_api_gateway_method.folders_id_files_options.http_method
  status_code         = aws_api_gateway_method_response.folders_id_files_options_200.status_code
  response_parameters = local.options_integration_response_params
  response_templates = {
    "application/json" = ""
  }
}

# ──────────────────────────────────────────────
# Methods - POST /folders/{id}/files
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "folders_id_files_post" {
  rest_api_id          = aws_api_gateway_rest_api.main.id
  resource_id          = aws_api_gateway_resource.folders_id_files.id
  http_method          = "POST"
  authorization        = "COGNITO_USER_POOLS"
  authorizer_id        = aws_api_gateway_authorizer.cognito.id
  authorization_scopes = ["email", "openid"]
}

resource "aws_api_gateway_integration" "folders_id_files_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.folders_id_files.id
  http_method             = aws_api_gateway_method.folders_id_files_post.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.upload_handler.arn}/invocations"
}

resource "aws_api_gateway_method_response" "folders_id_files_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.folders_id_files.id
  http_method = aws_api_gateway_method.folders_id_files_post.http_method
  status_code = "200"
}

# ──────────────────────────────────────────────
# Methods - OPTIONS /folders/{id}/share
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "folders_id_share_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.folders_id_share.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "folders_id_share_options_200" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.folders_id_share.id
  http_method         = aws_api_gateway_method.folders_id_share_options.http_method
  status_code         = "200"
  response_parameters = local.options_method_response_params
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "folders_id_share_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.folders_id_share.id
  http_method = aws_api_gateway_method.folders_id_share_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "folders_id_share_options" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.folders_id_share.id
  http_method         = aws_api_gateway_method.folders_id_share_options.http_method
  status_code         = aws_api_gateway_method_response.folders_id_share_options_200.status_code
  response_parameters = local.options_integration_response_params
  response_templates = {
    "application/json" = ""
  }
}

# ──────────────────────────────────────────────
# Methods - POST /folders/{id}/share
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "folders_id_share_post" {
  rest_api_id          = aws_api_gateway_rest_api.main.id
  resource_id          = aws_api_gateway_resource.folders_id_share.id
  http_method          = "POST"
  authorization        = "COGNITO_USER_POOLS"
  authorizer_id        = aws_api_gateway_authorizer.cognito.id
  authorization_scopes = ["email", "openid"]
}

resource "aws_api_gateway_integration" "folders_id_share_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.folders_id_share.id
  http_method             = aws_api_gateway_method.folders_id_share_post.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.share_link_generator.arn}/invocations"
}

resource "aws_api_gateway_method_response" "folders_id_share_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.folders_id_share.id
  http_method = aws_api_gateway_method.folders_id_share_post.http_method
  status_code = "200"
}

# ──────────────────────────────────────────────
# Methods - /share/{token} (no auth)
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "share_token_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.share_token.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "share_token_get" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.share_token.id
  http_method             = aws_api_gateway_method.share_token_get.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.public_access_handler.arn}/invocations"
}

resource "aws_api_gateway_method_response" "share_token_get" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.share_token.id
  http_method = aws_api_gateway_method.share_token_get.http_method
  status_code = "200"
}

resource "aws_api_gateway_method" "share_token_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.share_token.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "share_token_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.share_token.id
  http_method             = aws_api_gateway_method.share_token_post.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.public_access_handler.arn}/invocations"
}

resource "aws_api_gateway_method_response" "share_token_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.share_token.id
  http_method = aws_api_gateway_method.share_token_post.http_method
  status_code = "200"
}

resource "aws_api_gateway_method" "share_token_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.share_token.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "share_token_options_200" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.share_token.id
  http_method         = aws_api_gateway_method.share_token_options.http_method
  status_code         = "200"
  response_parameters = local.options_method_response_params
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "share_token_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.share_token.id
  http_method = aws_api_gateway_method.share_token_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "share_token_options" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.share_token.id
  http_method         = aws_api_gateway_method.share_token_options.http_method
  status_code         = aws_api_gateway_method_response.share_token_options_200.status_code
  response_parameters = local.options_integration_response_params
  response_templates = {
    "application/json" = ""
  }
}

# ──────────────────────────────────────────────
# Methods - /share/{token}/verify (no auth)
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "share_token_verify_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.share_token_verify.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "share_token_verify_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.share_token_verify.id
  http_method             = aws_api_gateway_method.share_token_verify_post.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.public_access_handler.arn}/invocations"
}

resource "aws_api_gateway_method_response" "share_token_verify_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.share_token_verify.id
  http_method = aws_api_gateway_method.share_token_verify_post.http_method
  status_code = "200"
}

resource "aws_api_gateway_method" "share_token_verify_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.share_token_verify.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "share_token_verify_options_200" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.share_token_verify.id
  http_method         = aws_api_gateway_method.share_token_verify_options.http_method
  status_code         = "200"
  response_parameters = local.options_method_response_params
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "share_token_verify_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.share_token_verify.id
  http_method = aws_api_gateway_method.share_token_verify_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "share_token_verify_options" {
  rest_api_id         = aws_api_gateway_rest_api.main.id
  resource_id         = aws_api_gateway_resource.share_token_verify.id
  http_method         = aws_api_gateway_method.share_token_verify_options.http_method
  status_code         = aws_api_gateway_method_response.share_token_verify_options_200.status_code
  response_parameters = local.options_integration_response_params
  response_templates = {
    "application/json" = ""
  }
}

# ──────────────────────────────────────────────
# Methods - /webdav/{proxy+} (ANY + OPTIONS)
# ──────────────────────────────────────────────

resource "aws_api_gateway_method" "webdav_proxy_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.webdav_proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "webdav_proxy_any" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.webdav_proxy.id
  http_method             = aws_api_gateway_method.webdav_proxy_any.http_method
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "${local.lambda_invoke_arn}${aws_lambda_function.webdav_handler.arn}/invocations"
}

resource "aws_api_gateway_method_response" "webdav_proxy_any" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.webdav_proxy.id
  http_method = aws_api_gateway_method.webdav_proxy_any.http_method
  status_code = "200"
}

resource "aws_api_gateway_method" "webdav_proxy_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.webdav_proxy.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "webdav_proxy_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.webdav_proxy.id
  http_method = aws_api_gateway_method.webdav_proxy_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers"  = true
    "method.response.header.Access-Control-Allow-Methods"  = true
    "method.response.header.Access-Control-Allow-Origin"   = true
    "method.response.header.Access-Control-Expose-Headers" = true
  }
  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "webdav_proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.webdav_proxy.id
  http_method = aws_api_gateway_method.webdav_proxy_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration_response" "webdav_proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.webdav_proxy.id
  http_method = aws_api_gateway_method.webdav_proxy_options.http_method
  status_code = aws_api_gateway_method_response.webdav_proxy_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers"  = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,Depth,Overwrite,Destination'"
    "method.response.header.Access-Control-Allow-Methods"  = "'GET,HEAD,PUT,POST,DELETE,OPTIONS,PROPFIND,PROPPATCH,MKCOL,COPY,MOVE,LOCK,UNLOCK'"
    "method.response.header.Access-Control-Allow-Origin"   = "'https://${aws_cloudfront_distribution.main.domain_name}'"
    "method.response.header.Access-Control-Expose-Headers" = "'DAV'"
  }
  response_templates = {
    "application/json" = ""
  }
}

# ──────────────────────────────────────────────
# Deployment
# ──────────────────────────────────────────────

resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_integration.folders_post,
    aws_api_gateway_integration.folders_id_files_post,
    aws_api_gateway_integration.folders_id_share_post,
    aws_api_gateway_integration.share_token_get,
    aws_api_gateway_integration.share_token_post,
    aws_api_gateway_integration.share_token_verify_post,
    aws_api_gateway_integration.webdav_proxy_any,
    aws_api_gateway_integration.folders_options,
    aws_api_gateway_integration.folders_id_files_options,
    aws_api_gateway_integration.folders_id_share_options,
    aws_api_gateway_integration.share_token_options,
    aws_api_gateway_integration.share_token_verify_options,
    aws_api_gateway_integration.webdav_proxy_options,
  ]

  rest_api_id = aws_api_gateway_rest_api.main.id
  description = "Deployment for ${var.environment}"

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_rest_api.main.body,
      aws_api_gateway_integration.folders_post,
      aws_api_gateway_integration.folders_id_files_post,
      aws_api_gateway_integration.folders_id_share_post,
      aws_api_gateway_integration.share_token_get,
      aws_api_gateway_integration.share_token_post,
      aws_api_gateway_integration.share_token_verify_post,
      aws_api_gateway_integration.webdav_proxy_any,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  stage_name    = var.environment
  rest_api_id   = aws_api_gateway_rest_api.main.id
  deployment_id = aws_api_gateway_deployment.main.id

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId          = "$context.requestId"
      extendedRequestId  = "$context.extendedRequestId"
      ip                 = "$context.identity.sourceIp"
      userAgent          = "$context.identity.userAgent"
      method             = "$context.httpMethod"
      resourcePath       = "$context.resourcePath"
      status             = "$context.status"
      protocol           = "$context.protocol"
      responseLength     = "$context.responseLength"
      requestTime        = "$context.requestTime"
      authorizer         = "$context.authorizer.claims.sub"
      integrationStatus  = "$context.integrationStatus"
      integrationLatency = "$context.integration.latency"
    })
  }
}

# ──────────────────────────────────────────────
# Lambda Permissions for API Gateway
# ──────────────────────────────────────────────

resource "aws_lambda_permission" "folder_manager_apigw" {
  statement_id  = "AllowAPIGatewayInvokeFolderManager"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.folder_manager.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/POST/folders"
}

resource "aws_lambda_permission" "upload_handler_apigw" {
  statement_id  = "AllowAPIGatewayInvokeUploadHandler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.upload_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/POST/folders/*/files"
}

resource "aws_lambda_permission" "share_link_generator_apigw" {
  statement_id  = "AllowAPIGatewayInvokeShareLinkGenerator"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.share_link_generator.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/POST/folders/*/share"
}

resource "aws_lambda_permission" "public_access_handler_get_apigw" {
  statement_id  = "AllowAPIGatewayInvokePublicAccessGet"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.public_access_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/GET/share/*"
}

resource "aws_lambda_permission" "public_access_handler_post_apigw" {
  statement_id  = "AllowAPIGatewayInvokePublicAccessPost"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.public_access_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/POST/share/*"
}

resource "aws_lambda_permission" "public_access_handler_verify_apigw" {
  statement_id  = "AllowAPIGatewayInvokePublicAccessVerify"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.public_access_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/POST/share/*/verify"
}

resource "aws_lambda_permission" "webdav_handler_apigw" {
  statement_id  = "AllowAPIGatewayInvokeWebDAV"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webdav_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/ANY/webdav/*"
}
