data "archive_file" "lambda_ai_agent_control" {
  type        = "zip"
  output_path = "${path.module}/lambda_ai_agent_control.zip"

  source {
    content  = <<-EOF
import json
import boto3
import os
import logging
import base64
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError, WaiterError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client('ec2')
dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

AI_AGENT_INSTANCE_ID = os.environ['AI_AGENT_INSTANCE_ID']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
HEARTBEAT_TIMEOUT = int(os.environ.get('HEARTBEAT_TIMEOUT_MINUTES', '5'))

def get_table():
    return dynamodb.Table(DYNAMODB_TABLE)

def get_instance_state():
    try:
        response = ec2.describe_instances(InstanceIds=[AI_AGENT_INSTANCE_ID])
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

def start_ai_agent():
    try:
        instance_info = get_instance_state()
        current_state = instance_info['state']
        
        if current_state == 'running':
            logger.info("Instance already running")
            return {
                'status': 'already_running',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'private_ip': instance_info['private_ip'],
                'public_ip': instance_info['public_ip'],
                'message': 'AI Agent is already running'
            }
        
        if current_state in ['stopping', 'stopped']:
            if current_state == 'stopping':
                logger.warning("Instance is stopping, cannot start")
                return {
                    'status': 'stopping',
                    'instance_id': AI_AGENT_INSTANCE_ID,
                    'message': 'AI Agent is currently stopping, please wait'
                }
        
        logger.info(f"Starting instance {AI_AGENT_INSTANCE_ID}")
        ec2.start_instances(InstanceIds=[AI_AGENT_INSTANCE_ID])
        
        waiter = ec2.get_waiter('instance_running')
        try:
            waiter.wait(
                InstanceIds=[AI_AGENT_INSTANCE_ID],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 12}
            )
            logger.info("Instance started successfully")
        except WaiterError as e:
            logger.error(f"Timeout waiting for instance to start: {e}")
            return {
                'status': 'starting',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'message': f'Instance is starting but timeout occurred: {str(e)}'
            }
        
        instance_info = get_instance_state()
        
        update_heartbeat()
        
        return {
            'status': 'started',
            'instance_id': AI_AGENT_INSTANCE_ID,
            'private_ip': instance_info['private_ip'],
            'public_ip': instance_info['public_ip'],
            'message': 'AI Agent started successfully'
        }
    except ClientError as e:
        logger.error(f"Error starting instance: {e}")
        raise

def stop_ai_agent():
    try:
        instance_info = get_instance_state()
        current_state = instance_info['state']
        
        if current_state == 'stopped':
            logger.info("Instance already stopped")
            return {
                'status': 'already_stopped',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'message': 'AI Agent is already stopped'
            }
        
        if current_state == 'stopping':
            logger.info("Instance is already stopping")
            return {
                'status': 'stopping',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'message': 'AI Agent is already stopping'
            }
        
        if current_state not in ['running', 'pending']:
            return {
                'status': 'error',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'message': f'Cannot stop instance in state: {current_state}'
            }
        
        logger.info(f"Stopping instance {AI_AGENT_INSTANCE_ID}")
        ec2.stop_instances(InstanceIds=[AI_AGENT_INSTANCE_ID])
        
        waiter = ec2.get_waiter('instance_stopped')
        try:
            waiter.wait(
                InstanceIds=[AI_AGENT_INSTANCE_ID],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 12}
            )
            logger.info("Instance stopped successfully")
        except WaiterError as e:
            logger.error(f"Timeout waiting for instance to stop: {e}")
            return {
                'status': 'stopping',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'message': f'Instance is stopping but timeout occurred: {str(e)}'
            }
        
        return {
            'status': 'stopped',
            'instance_id': AI_AGENT_INSTANCE_ID,
            'message': 'AI Agent stopped successfully'
        }
    except ClientError as e:
        logger.error(f"Error stopping instance: {e}")
        raise

def update_heartbeat():
    try:
        table = get_table()
        now = datetime.now(timezone.utc)
        
        table.put_item(
            Item={
                'instance_id': AI_AGENT_INSTANCE_ID,
                'last_heartbeat': now.isoformat(),
                'ttl': int((now.timestamp() + (HEARTBEAT_TIMEOUT * 60 * 2)))
            }
        )
        
        logger.info("Heartbeat updated")
        return {
            'status': 'ok',
            'instance_id': AI_AGENT_INSTANCE_ID,
            'last_heartbeat': now.isoformat()
        }
    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}")
        raise

def check_activity():
    import requests
    import os
    
    ai_agent_api_url = os.environ.get('AI_AGENT_API_URL', '')
    if not ai_agent_api_url:
        logger.warning("AI_AGENT_API_URL not configured, skipping activity check")
        return None
    
    try:
        response = requests.get(f"{ai_agent_api_url}/activity/check", timeout=5)
        if response.status_code == 200:
            return response.json()
        logger.warning(f"Activity check returned {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Activity check failed: {e}")
        return None

def check_heartbeat():
    try:
        table = get_table()
        response = table.get_item(
            Key={'instance_id': AI_AGENT_INSTANCE_ID}
        )
        
        instance_info = get_instance_state()
        
        if instance_info['state'] != 'running':
            return {
                'status': 'stopped',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'state': instance_info['state']
            }
        
        activity_data = check_activity()
        if activity_data:
            idle_minutes = activity_data.get('idle_minutes', 0)
            should_shutdown = activity_data.get('should_shutdown', False)
            
            if should_shutdown:
                logger.info(f"Stopping instance due to inactivity: {idle_minutes:.1f} minutes idle")
                return stop_ai_agent()
        
        if 'Item' not in response:
            logger.warning("No heartbeat found, checking activity")
            if not activity_data or not activity_data.get('has_activity'):
                logger.info("No activity found, stopping instance")
                return stop_ai_agent()
            return {
                'status': 'no_heartbeat',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'state': instance_info['state'],
                'has_activity': activity_data.get('has_activity', False)
            }
        
        last_heartbeat_str = response['Item']['last_heartbeat']
        last_heartbeat = datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff_minutes = (now - last_heartbeat).total_seconds() / 60
        
        if diff_minutes > HEARTBEAT_TIMEOUT:
            logger.warning(f"Heartbeat timeout: {diff_minutes:.1f} minutes")
            if not activity_data or not activity_data.get('has_activity'):
                logger.info("Stopping instance due to heartbeat timeout and no activity")
                return stop_ai_agent()
            return {
                'status': 'heartbeat_timeout',
                'instance_id': AI_AGENT_INSTANCE_ID,
                'state': instance_info['state'],
                'minutes_since_heartbeat': round(diff_minutes, 1),
                'has_activity': activity_data.get('has_activity', False)
            }
        
        logger.info(f"Heartbeat OK: {diff_minutes:.1f} minutes ago")
        return {
            'status': 'ok',
            'instance_id': AI_AGENT_INSTANCE_ID,
            'minutes_since_heartbeat': round(diff_minutes, 1),
            'activity': activity_data
        }
    except Exception as e:
        logger.error(f"Error checking heartbeat: {e}")
        raise

def get_status():
    instance_info = get_instance_state()
    
    try:
        table = get_table()
        response = table.get_item(
            Key={'instance_id': AI_AGENT_INSTANCE_ID}
        )
        
        heartbeat_info = {'status': 'unknown'}
        if 'Item' in response:
            last_heartbeat_str = response['Item']['last_heartbeat']
            last_heartbeat = datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            diff_minutes = (now - last_heartbeat).total_seconds() / 60
            
            heartbeat_info = {
                'status': 'active' if diff_minutes <= HEARTBEAT_TIMEOUT else 'timeout',
                'last_heartbeat': last_heartbeat_str,
                'minutes_ago': round(diff_minutes, 1),
                'will_stop_in': max(0, round(HEARTBEAT_TIMEOUT - diff_minutes, 1))
            }
    except Exception as e:
        logger.warning(f"Could not get heartbeat info: {e}")
        heartbeat_info = {'status': 'error', 'error': str(e)}
    
    return {
        'instance_id': AI_AGENT_INSTANCE_ID,
        'state': instance_info['state'],
        'private_ip': instance_info['private_ip'],
        'public_ip': instance_info['public_ip'],
        'heartbeat': heartbeat_info
    }

def find_ai_agent_instance():
    try:
        response = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:Role', 'Values': ['ai-agent']},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        
        if not response['Reservations']:
            raise ValueError("No running AI agent instance found")
        
        instance = response['Reservations'][0]['Instances'][0]
        instance_id = instance['InstanceId']
        logger.info(f"Found AI agent instance: {instance_id}")
        return instance_id
    except ClientError as e:
        logger.error(f"Error finding instance: {e}")
        raise

def deploy_ai_agent(env_vars_b64):
    instance_id = find_ai_agent_instance()
    commands = [
        "cd /opt/ai-agent",
        "git fetch origin",
        "git reset --hard origin/main",
        "pip3 install -r requirements.txt --quiet",
        "chmod +x update_env.py || true",
        f"python3 update_env.py \"{env_vars_b64}\"",
        "if ! grep -q '^CURSOR_API_KEY=' .env || [ -z \"$(grep '^CURSOR_API_KEY=' .env | cut -d= -f2)\" ]; then echo 'Error: CURSOR_API_KEY not set' && exit 1; fi",
        "if ! grep -q '^POSTGRES_PASSWORD=' .env || [ -z \"$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)\" ]; then echo 'Error: POSTGRES_PASSWORD not set' && exit 1; fi",
        "sudo systemctl restart ai-agent",
        "sleep 2",
        "sudo systemctl status ai-agent --no-pager"
    ]
    
    try:
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={
                'commands': commands
            },
            TimeoutSeconds=300
        )
        
        command_id = response['Command']['CommandId']
        logger.info(f"SSM command sent: {command_id}")
        
        waiter = ssm.get_waiter('command_executed')
        waiter.wait(
            CommandId=command_id,
            InstanceId=instance_id,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60}
        )
        
        output = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )
        
        return {
            'success': output.get('Status') == 'Success',
            'instance_id': instance_id,
            'command_id': command_id,
            'stdout': output.get('StandardOutputContent', ''),
            'stderr': output.get('StandardErrorContent', '')
        }
    except ClientError as e:
        logger.error(f"Error deploying: {e}")
        raise

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
    
    if 'action' in event:
        action = event['action']
    
    logger.info(f"Executing action: {action}")
    
    try:
        if action == 'start':
            result = start_ai_agent()
        elif action == 'stop':
            result = stop_ai_agent()
        elif action == 'heartbeat':
            result = update_heartbeat()
        elif action == 'check':
            result = check_heartbeat()
        elif action == 'deploy':
            env_vars = event.get('env_vars', {})
            if not env_vars:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'env_vars is required'})
                }
            env_json = json.dumps(env_vars)
            env_b64 = base64.b64encode(env_json.encode('utf-8')).decode('utf-8')
            deploy_result = deploy_ai_agent(env_b64)
            if deploy_result['success']:
                result = {
                    'success': True,
                    'instance_id': deploy_result['instance_id'],
                    'command_id': deploy_result['command_id'],
                    'output': deploy_result['stdout']
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'instance_id': deploy_result['instance_id'],
                        'command_id': deploy_result['command_id'],
                        'stdout': deploy_result['stdout'],
                        'stderr': deploy_result['stderr']
                    })
                }
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
  name = "${var.project_name}-lambda-ai-agent-control-ec2-policy"
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
  name = "${var.project_name}-lambda-ai-agent-control-dynamodb-policy"
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
  name = "${var.project_name}-lambda-ai-agent-control-ssm-policy"
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
  name = "${var.project_name}-lambda-ai-agent-control-logs-policy"
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
      AI_AGENT_INSTANCE_ID       = aws_instance.ai_agent.id
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
      ip              = "$context.identity.sourceIp"
      requestTime     = "$context.requestTime"
      httpMethod      = "$context.httpMethod"
      routeKey        = "$context.routeKey"
      status          = "$context.status"
      protocol        = "$context.protocol"
      responseLength  = "$context.responseLength"
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

resource "aws_lambda_permission" "ai_agent_control_github" {
  statement_id  = "AllowExecutionFromGitHubActions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_agent_control.function_name
  principal     = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
}

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
