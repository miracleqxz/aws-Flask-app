data "archive_file" "lambda_backend_control" {
  type        = "zip"
  output_path = "${path.module}/lambda_backend_control.zip"

  source {
    content  = <<-EOF
import json
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal

ec2 = boto3.client('ec2')
dynamodb = boto3.resource('dynamodb')

BACKEND_INSTANCE_ID = os.environ['BACKEND_INSTANCE_ID']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
HEARTBEAT_TIMEOUT = int(os.environ.get('HEARTBEAT_TIMEOUT_MINUTES', '5'))

def get_table():
    return dynamodb.Table(DYNAMODB_TABLE)

def get_instance_state():
    """Get current state of backend EC2 instance"""
    response = ec2.describe_instances(InstanceIds=[BACKEND_INSTANCE_ID])
    if response['Reservations']:
        instance = response['Reservations'][0]['Instances'][0]
        return {
            'state': instance['State']['Name'],
            'private_ip': instance.get('PrivateIpAddress', ''),
            'public_ip': instance.get('PublicIpAddress', '')
        }
    return {'state': 'unknown', 'private_ip': '', 'public_ip': ''}

def start_backend():
    """Start the backend EC2 instance"""
    instance_info = get_instance_state()
    
    if instance_info['state'] == 'running':
        return {
            'status': 'already_running',
            'instance_id': BACKEND_INSTANCE_ID,
            'private_ip': instance_info['private_ip'],
            'message': 'Backend is already running'
        }
    
    if instance_info['state'] == 'stopping':
        return {
            'status': 'stopping',
            'instance_id': BACKEND_INSTANCE_ID,
            'message': 'Backend is currently stopping, please wait'
        }
    
    # Start the instance
    ec2.start_instances(InstanceIds=[BACKEND_INSTANCE_ID])
    
    # Wait for instance to be running (max 60 seconds)
    waiter = ec2.get_waiter('instance_running')
    try:
        waiter.wait(
            InstanceIds=[BACKEND_INSTANCE_ID],
            WaiterConfig={'Delay': 5, 'MaxAttempts': 12}
        )
    except Exception as e:
        return {
            'status': 'starting',
            'instance_id': BACKEND_INSTANCE_ID,
            'message': f'Instance is starting: {str(e)}'
        }
    
    # Get updated instance info
    instance_info = get_instance_state()
    
    # Update heartbeat
    update_heartbeat()
    
    return {
        'status': 'started',
        'instance_id': BACKEND_INSTANCE_ID,
        'private_ip': instance_info['private_ip'],
        'message': 'Backend started successfully'
    }

def stop_backend():
    """Stop the backend EC2 instance"""
    instance_info = get_instance_state()
    
    if instance_info['state'] == 'stopped':
        return {
            'status': 'already_stopped',
            'instance_id': BACKEND_INSTANCE_ID,
            'message': 'Backend is already stopped'
        }
    
    # Stop the instance
    ec2.stop_instances(InstanceIds=[BACKEND_INSTANCE_ID])
    
    # Clear heartbeat
    table = get_table()
    table.delete_item(Key={'key': 'heartbeat'})
    
    return {
        'status': 'stopping',
        'instance_id': BACKEND_INSTANCE_ID,
        'message': 'Backend is stopping'
    }

def update_heartbeat():
    """Update the heartbeat timestamp"""
    table = get_table()
    now = datetime.now(timezone.utc)
    
    table.put_item(Item={
        'key': 'heartbeat',
        'timestamp': now.isoformat(),
        'epoch': Decimal(str(now.timestamp()))
    })
    
    return {
        'status': 'ok',
        'timestamp': now.isoformat()
    }

def check_heartbeat():
    """Check if heartbeat has timed out and stop backend if needed"""
    table = get_table()
    
    # Get current heartbeat
    response = table.get_item(Key={'key': 'heartbeat'})
    
    if 'Item' not in response:
        # No heartbeat, check if instance is running
        instance_info = get_instance_state()
        if instance_info['state'] == 'running':
            # No heartbeat but running - stop it
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
        # Timeout exceeded - stop backend
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
    """Get current backend status"""
    instance_info = get_instance_state()
    table = get_table()
    
    # Get heartbeat info
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
    """Main Lambda handler"""
    
    # Get action from event
    action = event.get('action', 'status')
    
    # Handle API Gateway events
    if 'httpMethod' in event:
        path = event.get('path', '')
        if '/start' in path:
            action = 'start'
        elif '/stop' in path:
            action = 'stop'
        elif '/heartbeat' in path:
            action = 'heartbeat'
        elif '/status' in path:
            action = 'status'
    
    # Handle EventBridge events
    if 'source' in event and event['source'] == 'aws.events':
        action = 'check'
    
    # Execute action
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
        
        # Return API Gateway compatible response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
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
  timeout       = 120
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

  tags = {
    Name        = var.lambda_function_name
    Project     = var.project_name
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda
  ]
}


resource "aws_apigatewayv2_api" "backend_control" {
  name          = "${var.project_name}-backend-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }

  tags = {
    Name        = "${var.project_name}-backend-api"
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.backend_control.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Name        = "${var.project_name}-backend-api-stage"
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.backend_control.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.backend_control.invoke_arn
  payload_format_version = "2.0"
}

# Routes
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

# Lambda permission for API Gateway
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

  tags = {
    Name        = "${var.project_name}-heartbeat-check"
    Project     = var.project_name
    Environment = var.environment
  }
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
