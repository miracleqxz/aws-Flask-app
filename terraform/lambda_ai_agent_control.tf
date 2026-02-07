data "archive_file" "lambda_ai_agent_control" {
  type        = "zip"
  source_file = "${path.module}/lambda_functions/ai_agent_control/lambda_function.py"
  output_path = "${path.module}/lambda_ai_agent_control.zip"
}

resource "aws_dynamodb_table" "ai_agent_state" {
  name         = "${var.project_name}-ai-agent-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "instance_id"

  attribute {
    name = "instance_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-ai-agent-state"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}

resource "aws_iam_role" "lambda_ai_agent_control" {
  name = "${var.project_name}-lambda-ai-agent-control-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-lambda-ai-agent-control-role"
    }
  )
}

resource "aws_iam_role_policy" "lambda_ai_agent_control_ec2" {
  role = aws_iam_role.lambda_ai_agent_control.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:DescribeInstanceStatus"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_ai_agent_control_dynamodb" {
  role = aws_iam_role.lambda_ai_agent_control.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.ai_agent_state.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_ai_agent_control_ssm" {
  role = aws_iam_role.lambda_ai_agent_control.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:document/AWS-RunShellScript",
          "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:SendCommand"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ssm:resourceTag/Role" = "ai-agent"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_ai_agent_control_logs" {
  role = aws_iam_role.lambda_ai_agent_control.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_ai_agent_function_name}:*"
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "lambda_ai_agent" {
  name              = "/aws/lambda/${var.lambda_ai_agent_function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-lambda-ai-agent-logs"
    }
  )
}

resource "aws_lambda_function" "ai_agent_control" {
  function_name = var.lambda_ai_agent_function_name
  role          = aws_iam_role.lambda_ai_agent_control.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 256

  filename         = data.archive_file.lambda_ai_agent_control.output_path
  source_code_hash = data.archive_file.lambda_ai_agent_control.output_base64sha256

  environment {
    variables = {
      AI_AGENT_INSTANCE_ID      = aws_instance.ai_agent.id
      DYNAMODB_TABLE            = aws_dynamodb_table.ai_agent_state.name
      HEARTBEAT_TIMEOUT_MINUTES = tostring(var.heartbeat_timeout_minutes)
      AI_AGENT_API_URL          = aws_apigatewayv2_api.ai_chat.api_endpoint
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name        = var.lambda_ai_agent_function_name
      Project     = var.project_name
      Environment = var.environment
    }
  )

  depends_on = [
    aws_cloudwatch_log_group.lambda_ai_agent,
    aws_apigatewayv2_api.ai_chat
  ]
}

# --- API Gateway ---

resource "aws_apigatewayv2_api" "ai_agent_control" {
  name          = "${var.project_name}-ai-agent-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins  = var.environment == "prod" ? [] : ["*"]
    allow_methods  = ["GET", "POST", "OPTIONS"]
    allow_headers  = ["content-type"]
    expose_headers = []
    max_age        = 300
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-ai-agent-api"
    }
  )
}

resource "aws_apigatewayv2_integration" "ai_agent_control" {
  api_id = aws_apigatewayv2_api.ai_agent_control.id

  integration_type   = "AWS_PROXY"
  integration_method = "POST"
  integration_uri    = aws_lambda_function.ai_agent_control.invoke_arn
}

resource "aws_apigatewayv2_route" "ai_agent_status" {
  api_id    = aws_apigatewayv2_api.ai_agent_control.id
  route_key = "GET /status"
  target    = "integrations/${aws_apigatewayv2_integration.ai_agent_control.id}"
}

resource "aws_apigatewayv2_route" "ai_agent_start" {
  api_id    = aws_apigatewayv2_api.ai_agent_control.id
  route_key = "POST /start"
  target    = "integrations/${aws_apigatewayv2_integration.ai_agent_control.id}"
}

resource "aws_apigatewayv2_route" "ai_agent_stop" {
  api_id    = aws_apigatewayv2_api.ai_agent_control.id
  route_key = "POST /stop"
  target    = "integrations/${aws_apigatewayv2_integration.ai_agent_control.id}"
}

resource "aws_apigatewayv2_route" "ai_agent_heartbeat" {
  api_id    = aws_apigatewayv2_api.ai_agent_control.id
  route_key = "POST /heartbeat"
  target    = "integrations/${aws_apigatewayv2_integration.ai_agent_control.id}"
}

resource "aws_apigatewayv2_stage" "ai_agent_default" {
  api_id      = aws_apigatewayv2_api.ai_agent_control.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.ai_agent_api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "ai_agent_api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-ai-agent-api"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-ai-agent-api-logs"
    }
  )
}

resource "aws_lambda_permission" "ai_agent_control_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_agent_control.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ai_agent_control.execution_arn}/*/*"
}

resource "aws_lambda_permission" "ai_agent_control_github" {
  statement_id  = "AllowExecutionFromGitHubActions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_agent_control.function_name
  principal     = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
}

# --- Monitoring ---

resource "aws_cloudwatch_metric_alarm" "lambda_ai_agent_errors" {
  alarm_name          = "${var.project_name}-lambda-ai-agent-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "This metric monitors lambda errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ai_agent_control.function_name
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-lambda-ai-agent-errors-alarm"
    }
  )
}

# --- Scheduled heartbeat check ---

resource "aws_cloudwatch_event_rule" "ai_agent_heartbeat_check" {
  name                = "${var.project_name}-ai-agent-heartbeat-check"
  description         = "Check AI agent heartbeat and activity periodically"
  schedule_expression = "rate(5 minutes)"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-ai-agent-heartbeat-check"
    }
  )
}

resource "aws_cloudwatch_event_target" "ai_agent_heartbeat_check" {
  rule      = aws_cloudwatch_event_rule.ai_agent_heartbeat_check.name
  target_id = "CheckAIAgentHeartbeat"
  arn       = aws_lambda_function.ai_agent_control.arn
}

resource "aws_lambda_permission" "ai_agent_heartbeat_check" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_agent_control.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ai_agent_heartbeat_check.arn
}
