data "archive_file" "lambda_ai_chat_proxy" {
  type        = "zip"
  source_file = "${path.module}/lambda_functions/ai_chat_proxy/lambda_function.py"
  output_path = "${path.module}/lambda_ai_chat_proxy.zip"
}

resource "aws_iam_role" "lambda_ai_chat_proxy" {
  name = "${var.project_name}-lambda-ai-chat-proxy-role"

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
      Name = "${var.project_name}-lambda-ai-chat-proxy-role"
    }
  )
}

resource "aws_iam_role_policy" "lambda_ai_chat_proxy_logs" {
  name = "${var.project_name}-lambda-ai-chat-proxy-logs-policy"
  role = aws_iam_role.lambda_ai_chat_proxy.id

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
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_ai_chat_proxy_function_name}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ai_chat_proxy_vpc" {
  role       = aws_iam_role.lambda_ai_chat_proxy.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_cloudwatch_log_group" "lambda_ai_chat_proxy" {
  name              = "/aws/lambda/${var.lambda_ai_chat_proxy_function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-lambda-ai-chat-proxy-logs"
    }
  )
}

resource "aws_lambda_function" "ai_chat_proxy" {
  function_name = var.lambda_ai_chat_proxy_function_name
  role          = aws_iam_role.lambda_ai_chat_proxy.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.12"
  timeout       = 60
  memory_size   = 128

  filename         = data.archive_file.lambda_ai_chat_proxy.output_path
  source_code_hash = data.archive_file.lambda_ai_chat_proxy.output_base64sha256

  vpc_config {
    subnet_ids         = aws_subnet.private_subnets[*].id
    security_group_ids = [aws_security_group.lambda_ai_chat_proxy.id]
  }

  environment {
    variables = {
      AI_AGENT_FLASK_URL = "http://${aws_instance.ai_agent.private_ip}:5000"
      API_KEY            = var.ai_chat_api_key
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name        = var.lambda_ai_chat_proxy_function_name
      Project     = var.project_name
      Environment = var.environment
    }
  )

  depends_on = [
    aws_cloudwatch_log_group.lambda_ai_chat_proxy,
    aws_iam_role_policy_attachment.lambda_ai_chat_proxy_vpc
  ]
}

# --- API Gateway ---

resource "aws_apigatewayv2_api" "ai_chat" {
  name          = "${var.project_name}-ai-chat-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins  = var.environment == "prod" ? [] : ["*"]
    allow_methods  = ["GET", "POST", "OPTIONS"]
    allow_headers  = ["content-type", "x-api-key"]
    expose_headers = []
    max_age        = 300
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-ai-chat-api"
    }
  )
}

resource "aws_apigatewayv2_integration" "ai_chat" {
  api_id = aws_apigatewayv2_api.ai_chat.id

  integration_type   = "AWS_PROXY"
  integration_method = "POST"
  integration_uri    = aws_lambda_function.ai_chat_proxy.invoke_arn
}

resource "aws_apigatewayv2_route" "ai_chat_health" {
  api_id    = aws_apigatewayv2_api.ai_chat.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.ai_chat.id}"
}

resource "aws_apigatewayv2_route" "ai_chat_activity_check" {
  api_id    = aws_apigatewayv2_api.ai_chat.id
  route_key = "GET /activity/check"
  target    = "integrations/${aws_apigatewayv2_integration.ai_chat.id}"
}

resource "aws_apigatewayv2_route" "ai_chat_post" {
  api_id    = aws_apigatewayv2_api.ai_chat.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.ai_chat.id}"
}

resource "aws_apigatewayv2_stage" "ai_chat_default" {
  api_id      = aws_apigatewayv2_api.ai_chat.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.ai_chat_api_gateway.arn
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

resource "aws_cloudwatch_log_group" "ai_chat_api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-ai-chat-api"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-ai-chat-api-logs"
    }
  )
}

resource "aws_lambda_permission" "ai_chat_proxy_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_chat_proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ai_chat.execution_arn}/*/*"
}
