data "archive_file" "lambda_backend_control" {
  type        = "zip"
  output_path = "${path.module}/lambda_backend_control.zip"

  source {
    content  = <<-EOF
import json
import boto3
import os
import logging
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError, WaiterError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client('ec2')
dynamodb = boto3.resource('dynamodb')

BACKEND_INSTANCE_ID = os.environ['BACKEND_INSTANCE_ID']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
HEARTBEAT_TIMEOUT = int(os.environ.get('HEARTBEAT_TIMEOUT_MINUTES', '5'))

def get_table():
    return dynamodb.Table(DYNAMODB_TABLE)

def get_instance_state():
    try:
        response = ec2.describe_instances(InstanceIds=[BACKEND_INSTANCE_ID])
        if response['Reservations']:
            instance = response['Reservations'][0]['Instances'][0]
            state_info = {
                'state': instance['State']['Name'],
                'private_ip': instance.get('PrivateIpAddress', ''),
                'public_ip': instance.get('PublicIpAddress', ''),
                'state_code': instance['State']['Code']
            }
            logger.info(f"Instance state: {state_info['state']}")
            return state_info
        logger.warning("No reservations found for instance")
        return {'state': 'unknown', 'private_ip': '', 'public_ip': '', 'state_code': 0}
    except ClientError as e:
        logger.error(f"Error describing instance: {e}")
        raise

def start_backend():
    try:
        instance_info = get_instance_state()
        current_state = instance_info['state']
        
        if current_state == 'running':
            logger.info("Instance already running")
            return {
                'status': 'already_running',
                'instance_id': BACKEND_INSTANCE_ID,
                'private_ip': instance_info['private_ip'],
                'message': 'Backend is already running'
            }
        
        if current_state in ['stopping', 'stopped']:
            if current_state == 'stopping':
                logger.warning("Instance is stopping, cannot start")
                return {
                    'status': 'stopping',
                    'instance_id': BACKEND_INSTANCE_ID,
                    'message': 'Backend is currently stopping, please wait'
                }
        
        logger.info(f"Starting instance {BACKEND_INSTANCE_ID}")
        ec2.start_instances(InstanceIds=[BACKEND_INSTANCE_ID])
        
        waiter = ec2.get_waiter('instance_running')
        try:
            waiter.wait(
                InstanceIds=[BACKEND_INSTANCE_ID],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 12}
            )
            logger.info("Instance started successfully")
        except WaiterError as e:
            logger.error(f"Timeout waiting for instance to start: {e}")
            return {
                'status': 'starting',
                'instance_id': BACKEND_INSTANCE_ID,
                'message': f'Instance is starting but timeout occurred: {str(e)}'
            }
        
        instance_info = get_instance_state()
        
        update_heartbeat()
        
        return {
            'status': 'started',
            'instance_id': BACKEND_INSTANCE_ID,
            'private_ip': instance_info['private_ip'],
            'message': 'Backend started successfully'
        }
    except ClientError as e:
        logger.error(f"Error starting instance: {e}")
        raise

def stop_backend():
    try:
        instance_info = get_instance_state()
        
        if instance_info['state'] == 'stopped':
            logger.info("Instance already stopped")
            return {
                'status': 'already_stopped',
                'instance_id': BACKEND_INSTANCE_ID,
                'message': 'Backend is already stopped'
            }
        
        logger.info(f"Stopping instance {BACKEND_INSTANCE_ID}")
        ec2.stop_instances(InstanceIds=[BACKEND_INSTANCE_ID])
        
        try:
            table = get_table()
            table.delete_item(Key={'key': 'heartbeat'})
            logger.info("Heartbeat cleared")
        except Exception as e:
            logger.warning(f"Failed to clear heartbeat: {e}")
        
        return {
            'status': 'stopping',
            'instance_id': BACKEND_INSTANCE_ID,
            'message': 'Backend is stopping'
        }
    except ClientError as e:
        logger.error(f"Error stopping instance: {e}")
        raise

def update_heartbeat():
    try:
        table = get_table()
        now = datetime.now(timezone.utc)
        
        table.put_item(Item={
            'key': 'heartbeat',
            'timestamp': now.isoformat(),
            'epoch': Decimal(str(now.timestamp()))
        })
        
        logger.info(f"Heartbeat updated: {now.isoformat()}")
        return {
            'status': 'ok',
            'timestamp': now.isoformat()
        }
    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}")
        raise

def check_heartbeat():
    table = get_table()
    
    response = table.get_item(Key={'key': 'heartbeat'})
    
    if 'Item' not in response:
        instance_info = get_instance_state()
        if instance_info['state'] == 'running':
            return stop_backend()
        return {
            'status': 'no_heartbeat',
            'action': 'none',
            'message': 'No heartbeat found, backend not running'
        }
    
    last_heartbeat = datetime.fromisoformat(response['Item']['timestamp'])
    now = datetime.now(timezone.utc)
    diff_minutes = (now - last_heartbeat).total_seconds() / 60
    
    if diff_minutes > HEARTBEAT_TIMEOUT:
        result = stop_backend()
        result['reason'] = f'Heartbeat timeout ({diff_minutes:.1f} min > {HEARTBEAT_TIMEOUT} min)'
        return result
    
    return {
        'status': 'ok',
        'action': 'none',
        'last_heartbeat': last_heartbeat.isoformat(),
        'minutes_since': round(diff_minutes, 1),
        'timeout_minutes': HEARTBEAT_TIMEOUT
    }

def get_status():
    instance_info = get_instance_state()
    table = get_table()
    
    response = table.get_item(Key={'key': 'heartbeat'})
    heartbeat_info = {}
    
    if 'Item' in response:
        last_heartbeat = datetime.fromisoformat(response['Item']['timestamp'])
        now = datetime.now(timezone.utc)
        diff_minutes = (now - last_heartbeat).total_seconds() / 60
        heartbeat_info = {
            'last_heartbeat': last_heartbeat.isoformat(),
            'minutes_since': round(diff_minutes, 1),
            'timeout_minutes': HEARTBEAT_TIMEOUT,
            'will_stop_in': max(0, round(HEARTBEAT_TIMEOUT - diff_minutes, 1))
        }
    
    return {
        'instance_id': BACKEND_INSTANCE_ID,
        'state': instance_info['state'],
        'private_ip': instance_info['private_ip'],
        'public_ip': instance_info['public_ip'],
        'heartbeat': heartbeat_info
    }

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    action = event.get('action', 'status')
    
    if 'requestContext' in event and 'http' in event['requestContext']:
        path = event.get('rawPath', event.get('path', ''))
        method = event.get('requestContext', {}).get('http', {}).get('method', '')
        
        if method == 'POST' and '/start' in path:
            action = 'start'
        elif method == 'POST' and '/stop' in path:
            action = 'stop'
        elif method == 'POST' and '/heartbeat' in path:
            action = 'heartbeat'
        elif method == 'GET' and '/status' in path:
            action = 'status'
    
    elif 'httpMethod' in event:
        path = event.get('path', '')
        if '/start' in path:
            action = 'start'
        elif '/stop' in path:
            action = 'stop'
        elif '/heartbeat' in path:
            action = 'heartbeat'
        elif '/status' in path:
            action = 'status'
    
    if 'source' in event and event['source'] == 'aws.events':
        action = 'check'
    
    logger.info(f"Executing action: {action}")
    
    try:
        if action == 'start':
            result = start_backend()
        elif action == 'stop':
            result = stop_backend()
        elif action == 'heartbeat':
            result = update_heartbeat()
        elif action == 'check':
            result = check_heartbeat()
        else:
            result = get_status()
        
        logger.info(f"Action completed successfully: {action}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(result, default=str)
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"AWS ClientError ({error_code}): {error_msg}")
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'status': 'error',
                'error_code': error_code,
                'message': error_msg
            })
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'status': 'error',
                'message': str(e)
            })
        }
EOF
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "backend_control" {
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_backend_control.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.12"
  timeout       = 60
  memory_size   = 128

  filename         = data.archive_file.lambda_backend_control.output_path
  source_code_hash = data.archive_file.lambda_backend_control.output_base64sha256

  environment {
    variables = {
      BACKEND_INSTANCE_ID       = aws_instance.backend.id
      DYNAMODB_TABLE            = aws_dynamodb_table.backend_state.name
      HEARTBEAT_TIMEOUT_MINUTES = tostring(var.heartbeat_timeout_minutes)
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name        = var.lambda_function_name
      Project     = var.project_name
      Environment = var.environment
    }
  )

  depends_on = [
    aws_cloudwatch_log_group.lambda
  ]
}


resource "aws_apigatewayv2_api" "backend_control" {
  name          = "${var.project_name}-backend-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins  = var.environment == "prod" ? [] : ["*"]
    allow_methods  = ["GET", "POST", "OPTIONS"]
    allow_headers  = ["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"]
    max_age        = 300
    expose_headers = []
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-backend-api"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.backend_control.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
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

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-backend-api-stage"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-backend-api"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-api-gateway-logs"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.backend_control.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.backend_control.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "start" {
  api_id    = aws_apigatewayv2_api.backend_control.id
  route_key = "POST /start"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "stop" {
  api_id    = aws_apigatewayv2_api.backend_control.id
  route_key = "POST /stop"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "heartbeat" {
  api_id    = aws_apigatewayv2_api.backend_control.id
  route_key = "POST /heartbeat"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "status" {
  api_id    = aws_apigatewayv2_api.backend_control.id
  route_key = "GET /status"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend_control.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.backend_control.execution_arn}/*/*"
}


resource "aws_cloudwatch_event_rule" "heartbeat_check" {
  name                = "${var.project_name}-heartbeat-check"
  description         = "Check backend heartbeat every minute"
  schedule_expression = "rate(${var.heartbeat_interval_seconds / 60} minute)"

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-heartbeat-check"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_event_target" "heartbeat_check" {
  rule      = aws_cloudwatch_event_rule.heartbeat_check.name
  target_id = "lambda"
  arn       = aws_lambda_function.backend_control.arn

  input = jsonencode({
    action = "check"
  })
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend_control.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.heartbeat_check.arn
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Lambda function errors exceed threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.backend_control.function_name
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-lambda-errors-alarm"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}
