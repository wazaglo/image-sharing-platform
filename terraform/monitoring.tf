resource "aws_sns_topic" "alarms" {
  name         = "ImageShare-Alarms-${var.environment}"
  display_name = "ImageShare Alarms ${var.environment}"
  tags = {
    Name        = "ImageShare-Alarms-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_sns_topic_subscription" "alarm_email" {
  protocol  = "email"
  endpoint  = var.alarm_email
  topic_arn = aws_sns_topic.alarms.arn
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "ImageShare-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = true
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.folder_manager.function_name, { label = "FolderManager" }],
            [".", "Invocations", ".", aws_lambda_function.upload_handler.function_name, { label = "UploadHandler" }],
            [".", "Invocations", ".", aws_lambda_function.share_link_generator.function_name, { label = "ShareLinkGenerator" }],
            [".", "Invocations", ".", aws_lambda_function.public_access_handler.function_name, { label = "PublicAccessHandler" }],
            [".", "Invocations", ".", aws_lambda_function.image_processor.function_name, { label = "ImageProcessor" }],
            [".", "Invocations", ".", aws_lambda_function.webdav_handler.function_name, { label = "WebDAVHandler" }],
          ]
          region = var.aws_region
          title  = "Lambda Invocations"
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = true
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.folder_manager.function_name, { label = "FolderManager" }],
            [".", "Errors", ".", aws_lambda_function.upload_handler.function_name, { label = "UploadHandler" }],
            [".", "Errors", ".", aws_lambda_function.share_link_generator.function_name, { label = "ShareLinkGenerator" }],
            [".", "Errors", ".", aws_lambda_function.public_access_handler.function_name, { label = "PublicAccessHandler" }],
            [".", "Errors", ".", aws_lambda_function.image_processor.function_name, { label = "ImageProcessor" }],
            [".", "Errors", ".", aws_lambda_function.webdav_handler.function_name, { label = "WebDAVHandler" }],
          ]
          region = var.aws_region
          title  = "Lambda Errors"
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.folder_manager.function_name, { label = "FolderManager", yAxis = "left" }],
            [".", "Duration", ".", aws_lambda_function.upload_handler.function_name, { label = "UploadHandler" }],
            [".", "Duration", ".", aws_lambda_function.share_link_generator.function_name, { label = "ShareLinkGenerator" }],
            [".", "Duration", ".", aws_lambda_function.public_access_handler.function_name, { label = "PublicAccessHandler" }],
            [".", "Duration", ".", aws_lambda_function.image_processor.function_name, { label = "ImageProcessor" }],
            [".", "Duration", ".", aws_lambda_function.webdav_handler.function_name, { label = "WebDAVHandler" }],
          ]
          region = var.aws_region
          title  = "Lambda Duration (ms)"
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/ApiGateway", "4XXError", "ApiName", aws_api_gateway_rest_api.main.name, { label = "4XX Errors", yAxis = "left" }],
            [".", "5XXError", ".", aws_api_gateway_rest_api.main.name, { label = "5XX Errors" }],
            [".", "Count", ".", aws_api_gateway_rest_api.main.name, { label = "Request Count", stat = "Sum", period = 300 }],
          ]
          region = var.aws_region
          title  = "API Gateway Errors & Requests"
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.folders.name, { label = "Folders (RCU)" }],
            [".", "ConsumedWriteCapacityUnits", ".", aws_dynamodb_table.folders.name, { label = "Folders (WCU)" }],
            [".", "ConsumedReadCapacityUnits", ".", aws_dynamodb_table.files.name, { label = "Files (RCU)" }],
            [".", "ConsumedWriteCapacityUnits", ".", aws_dynamodb_table.files.name, { label = "Files (WCU)" }],
            [".", "ConsumedReadCapacityUnits", ".", aws_dynamodb_table.shares.name, { label = "Shares (RCU)" }],
            [".", "ConsumedWriteCapacityUnits", ".", aws_dynamodb_table.shares.name, { label = "Shares (WCU)" }],
          ]
          region = var.aws_region
          title  = "DynamoDB Consumed Capacity"
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = true
          metrics = [
            ["AWS/DynamoDB", "ThrottledRequests", "TableName", aws_dynamodb_table.folders.name, { label = "Folders" }],
            [".", "ThrottledRequests", ".", aws_dynamodb_table.files.name, { label = "Files" }],
            [".", "ThrottledRequests", ".", aws_dynamodb_table.shares.name, { label = "Shares" }],
          ]
          region = var.aws_region
          title  = "DynamoDB Throttled Requests"
          period = 300
          stat   = "Sum"
        }
      },
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "ImageShare-LambdaErrors-${var.environment}"
  alarm_description   = "Lambda error count exceeded threshold for ${var.environment}"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.folder_manager.function_name
  }
  alarm_actions             = [aws_sns_topic.alarms.arn]
  ok_actions                = [aws_sns_topic.alarms.arn]
  insufficient_data_actions = [aws_sns_topic.alarms.arn]
  tags = {
    Name        = "ImageShare-LambdaErrors-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_5xx_errors" {
  alarm_name          = "ImageShare-Api5xxErrors-${var.environment}"
  alarm_description   = "API Gateway 5XX error count exceeded threshold for ${var.environment}"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
  }
  alarm_actions             = [aws_sns_topic.alarms.arn]
  ok_actions                = [aws_sns_topic.alarms.arn]
  insufficient_data_actions = [aws_sns_topic.alarms.arn]
  tags = {
    Name        = "ImageShare-Api5xxErrors-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttling" {
  alarm_name          = "ImageShare-DynamoDBThrottling-${var.environment}"
  alarm_description   = "DynamoDB throttled write events exceeded threshold for ${var.environment}"
  namespace           = "AWS/DynamoDB"
  metric_name         = "ThrottledRequests"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    TableName = aws_dynamodb_table.files.name
  }
  alarm_actions             = [aws_sns_topic.alarms.arn]
  ok_actions                = [aws_sns_topic.alarms.arn]
  insufficient_data_actions = [aws_sns_topic.alarms.arn]
  tags = {
    Name        = "ImageShare-DynamoDBThrottling-${var.environment}"
    Environment = var.environment
    Platform    = "ImageShare"
  }
}
