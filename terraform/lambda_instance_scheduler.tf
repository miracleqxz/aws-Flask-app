data "archive_file" "instance_scheduler" {
  type        = "zip"
  source_file = "${path.module}/lambda_functions/instance_scheduler/lambda_function.py"
  output_path = "${path.module}/lambda_instance_scheduler.zip"
}

resource "aws_iam_role" "lambda_instance_scheduler" {
  name = "${var.project_name}-lambda-scheduler-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole", Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_ec2" {
  role = aws_iam_role.lambda_instance_scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ec2:DescribeInstances", "ec2:StartInstances", "ec2:StopInstances"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_logs" {
  role = aws_iam_role.lambda_instance_scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-instance-scheduler:*"
    }]
  })
}

resource "aws_cloudwatch_log_group" "instance_scheduler" {
  name              = "/aws/lambda/${var.project_name}-instance-scheduler"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "instance_scheduler" {
  function_name    = "${var.project_name}-instance-scheduler"
  role             = aws_iam_role.lambda_instance_scheduler.arn
  handler          = "lambda_function.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 128
  filename         = data.archive_file.instance_scheduler.output_path
  source_code_hash = data.archive_file.instance_scheduler.output_base64sha256

  environment {
    variables = {
      BACKEND_INSTANCE_ID  = aws_instance.backend.id
      AI_AGENT_INSTANCE_ID = aws_instance.ai_agent.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.instance_scheduler]
}

# Start at 08:00 local (UTC adjusted)
resource "aws_cloudwatch_event_rule" "scheduler_start" {
  name                = "${var.project_name}-scheduler-start"
  schedule_expression = "cron(0 ${var.scheduler_start_hour_utc} ? * * *)"
}

resource "aws_cloudwatch_event_target" "scheduler_start" {
  rule      = aws_cloudwatch_event_rule.scheduler_start.name
  target_id = "StartInstances"
  arn       = aws_lambda_function.instance_scheduler.arn
  input     = jsonencode({ action = "start" })
}

resource "aws_lambda_permission" "scheduler_start" {
  statement_id  = "AllowEventBridgeStart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.instance_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduler_start.arn
}

# Stop at 00:00 local (midnight, UTC adjusted)
resource "aws_cloudwatch_event_rule" "scheduler_stop" {
  name                = "${var.project_name}-scheduler-stop"
  schedule_expression = "cron(0 ${var.scheduler_stop_hour_utc} ? * * *)"
}

resource "aws_cloudwatch_event_target" "scheduler_stop" {
  rule      = aws_cloudwatch_event_rule.scheduler_stop.name
  target_id = "StopInstances"
  arn       = aws_lambda_function.instance_scheduler.arn
  input     = jsonencode({ action = "stop" })
}

resource "aws_lambda_permission" "scheduler_stop" {
  statement_id  = "AllowEventBridgeStop"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.instance_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduler_stop.arn
}

# API Gateway for manual control
resource "aws_apigatewayv2_api" "scheduler" {
  name          = "${var.project_name}-scheduler-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "scheduler" {
  api_id      = aws_apigatewayv2_api.scheduler.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "scheduler" {
  api_id                 = aws_apigatewayv2_api.scheduler.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.instance_scheduler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "scheduler_status" {
  api_id    = aws_apigatewayv2_api.scheduler.id
  route_key = "GET /status"
  target    = "integrations/${aws_apigatewayv2_integration.scheduler.id}"
}

resource "aws_apigatewayv2_route" "scheduler_start" {
  api_id    = aws_apigatewayv2_api.scheduler.id
  route_key = "POST /start"
  target    = "integrations/${aws_apigatewayv2_integration.scheduler.id}"
}

resource "aws_apigatewayv2_route" "scheduler_stop" {
  api_id    = aws_apigatewayv2_api.scheduler.id
  route_key = "POST /stop"
  target    = "integrations/${aws_apigatewayv2_integration.scheduler.id}"
}

resource "aws_lambda_permission" "scheduler_apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.instance_scheduler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.scheduler.execution_arn}/*/*"
}
