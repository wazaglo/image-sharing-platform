locals {
  lambda_source_base = "${path.module}/../src/backend"
  lambda_functions = {
    folder_manager        = "folder_manager"
    upload_handler        = "upload_handler"
    share_link_generator  = "share_link_generator"
    public_access_handler = "public_access_handler"
    image_processor       = "image_processor"
    webdav_handler        = "webdav_handler"
  }
  account_id = data.aws_caller_identity.current.account_id
}

data "aws_caller_identity" "current" {}

resource "aws_sqs_queue" "thumbnail_errors" {
  name                       = "ImageShare-ThumbnailErrors-${var.environment}"
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 300
  tags = {
    Name        = "ImageShare-ThumbnailErrors-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_iam_role" "lambda" {
  name = "ImageShare-LambdaRole-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "ImageShare-LambdaRole-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda" {
  name = "ImageShareLambdaPolicy-${var.environment}"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:CopyObject",
          "s3:ListBucket",
          "s3:GetObjectAttributes",
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*",
        ]
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
        ]
        Resource = [
          aws_dynamodb_table.folders.arn,
          aws_dynamodb_table.files.arn,
          aws_dynamodb_table.shares.arn,
        ]
      },
      {
        Sid    = "DynamoDBIndexAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = [
          "${aws_dynamodb_table.folders.arn}/index/*",
          "${aws_dynamodb_table.files.arn}/index/*",
          "${aws_dynamodb_table.shares.arn}/index/*",
        ]
      },
      {
        Sid    = "CognitoAccess"
        Effect = "Allow"
        Action = [
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminUpdateUserAttributes",
          "cognito-idp:AdminDeleteUser",
          "cognito-idp:ListUsers",
          "cognito-idp:AdminInitiateAuth",
          "cognito-idp:AdminRespondToAuthChallenge",
        ]
        Resource = [aws_cognito_user_pool.main.arn]
      },
      {
        Sid    = "SQSAccess"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = [aws_sqs_queue.thumbnail_errors.arn]
      },
    ]
  })
}

resource "terraform_data" "build_lambda_zips" {
  triggers_replace = {
    folder_manager  = filesha256("${local.lambda_source_base}/lambdas/folder_manager/handler.py")
    upload_handler  = filesha256("${local.lambda_source_base}/lambdas/upload_handler/handler.py")
    share_generator = filesha256("${local.lambda_source_base}/lambdas/share_link_generator/handler.py")
    public_access   = filesha256("${local.lambda_source_base}/lambdas/public_access_handler/handler.py")
    image_processor = filesha256("${local.lambda_source_base}/lambdas/image_processor/handler.py")
    webdav          = filesha256("${local.lambda_source_base}/lambdas/webdav_handler/handler.py")
    config          = filesha256("${local.lambda_source_base}/shared/config.py")
    utils           = filesha256("${local.lambda_source_base}/shared/utils.py")
    init            = filesha256("${local.lambda_source_base}/shared/__init__.py")
  }

  provisioner "local-exec" {
    command = <<EOT
      ZIPS="${path.module}/lambda-zips"
      SRC="${local.lambda_source_base}"
      mkdir -p "$ZIPS"
      for func in folder_manager upload_handler share_link_generator public_access_handler image_processor webdav_handler; do
        build_dir="/tmp/lambda-build-$func"
        rm -rf "$build_dir"
        mkdir -p "$build_dir"
        cp "$SRC/lambdas/$func/handler.py" "$build_dir/"
        cp "$SRC/shared/"*.py "$build_dir/"
        (cd "$build_dir" && zip -r9 "$ZIPS/$func.zip" .)
      done
EOT
  }
}

resource "aws_cloudwatch_log_group" "folder_manager" {
  name              = "/aws/lambda/ImageShare-FolderManager-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "upload_handler" {
  name              = "/aws/lambda/ImageShare-UploadHandler-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "share_link_generator" {
  name              = "/aws/lambda/ImageShare-ShareLinkGenerator-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "public_access_handler" {
  name              = "/aws/lambda/ImageShare-PublicAccessHandler-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "image_processor" {
  name              = "/aws/lambda/ImageShare-ImageProcessor-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "webdav_handler" {
  name              = "/aws/lambda/ImageShare-WebDAVHandler-${var.environment}"
  retention_in_days = var.log_retention_days
}

locals {
  lambda_env = {
    BUCKET_NAME       = var.bucket_name
    FOLDERS_TABLE     = aws_dynamodb_table.folders.name
    FILES_TABLE       = aws_dynamodb_table.files.name
    SHARES_TABLE      = aws_dynamodb_table.shares.name
    USERS_PREFIX      = var.users_prefix
    THUMBNAIL_PREFIX  = var.thumbnail_prefix
    CLOUDFRONT_DOMAIN = aws_cloudfront_distribution.main.domain_name
    LOG_LEVEL         = var.log_level
  }
  lambda_env_with_admin = merge(local.lambda_env, {
    ADMIN_EMAILS = var.admin_emails
  })
}

resource "aws_lambda_function" "folder_manager" {
  depends_on = [terraform_data.build_lambda_zips]

  function_name                  = "ImageShare-FolderManager-${var.environment}"
  role                           = aws_iam_role.lambda.arn
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  architectures                  = ["arm64"]
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 5

  filename         = "${path.module}/lambda-zips/folder_manager.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda-zips/folder_manager.zip")

  dead_letter_config {
    target_arn = aws_sqs_queue.thumbnail_errors.arn
  }

  environment {
    variables = local.lambda_env_with_admin
  }

  tags = {
    Name        = "ImageShare-FolderManager-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_lambda_function" "upload_handler" {
  depends_on = [terraform_data.build_lambda_zips]

  function_name                  = "ImageShare-UploadHandler-${var.environment}"
  role                           = aws_iam_role.lambda.arn
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  architectures                  = ["arm64"]
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 5

  filename         = "${path.module}/lambda-zips/upload_handler.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda-zips/upload_handler.zip")

  dead_letter_config {
    target_arn = aws_sqs_queue.thumbnail_errors.arn
  }

  environment {
    variables = local.lambda_env
  }

  tags = {
    Name        = "ImageShare-UploadHandler-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_lambda_function" "share_link_generator" {
  depends_on = [terraform_data.build_lambda_zips]

  function_name                  = "ImageShare-ShareLinkGenerator-${var.environment}"
  role                           = aws_iam_role.lambda.arn
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  architectures                  = ["arm64"]
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 5

  filename         = "${path.module}/lambda-zips/share_link_generator.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda-zips/share_link_generator.zip")

  dead_letter_config {
    target_arn = aws_sqs_queue.thumbnail_errors.arn
  }

  environment {
    variables = local.lambda_env
  }

  tags = {
    Name        = "ImageShare-ShareLinkGenerator-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_lambda_function" "public_access_handler" {
  depends_on = [terraform_data.build_lambda_zips]

  function_name                  = "ImageShare-PublicAccessHandler-${var.environment}"
  role                           = aws_iam_role.lambda.arn
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  architectures                  = ["arm64"]
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 5

  filename         = "${path.module}/lambda-zips/public_access_handler.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda-zips/public_access_handler.zip")

  dead_letter_config {
    target_arn = aws_sqs_queue.thumbnail_errors.arn
  }

  environment {
    variables = local.lambda_env
  }

  tags = {
    Name        = "ImageShare-PublicAccessHandler-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_lambda_function" "image_processor" {
  depends_on = [terraform_data.build_lambda_zips]

  function_name                  = "ImageShare-ImageProcessor-${var.environment}"
  role                           = aws_iam_role.lambda.arn
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  architectures                  = ["arm64"]
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 5

  filename         = "${path.module}/lambda-zips/image_processor.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda-zips/image_processor.zip")

  dead_letter_config {
    target_arn = aws_sqs_queue.thumbnail_errors.arn
  }

  environment {
    variables = local.lambda_env
  }

  tags = {
    Name        = "ImageShare-ImageProcessor-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_lambda_function" "webdav_handler" {
  depends_on = [terraform_data.build_lambda_zips]

  function_name                  = "ImageShare-WebDAVHandler-${var.environment}"
  role                           = aws_iam_role.lambda.arn
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  architectures                  = ["arm64"]
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 5

  filename         = "${path.module}/lambda-zips/webdav_handler.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda-zips/webdav_handler.zip")

  dead_letter_config {
    target_arn = aws_sqs_queue.thumbnail_errors.arn
  }

  environment {
    variables = local.lambda_env
  }

  tags = {
    Name        = "ImageShare-WebDAVHandler-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_cloudwatch_event_rule" "image_upload" {
  name        = "ImageShare-ImageUpload-${var.environment}"
  description = "Triggers ImageProcessor on new image uploads"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.bucket_name]
      }
      object = {
        key = [{
          prefix = var.users_prefix
        }]
      }
    }
  })

  state = "ENABLED"

  tags = {
    Name        = "ImageShare-ImageUpload-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_cloudwatch_event_target" "image_processor" {
  rule = aws_cloudwatch_event_rule.image_upload.name
  arn  = aws_lambda_function.image_processor.arn
}

resource "aws_lambda_permission" "eventbridge_invoke_image_processor" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.image_upload.arn
}
