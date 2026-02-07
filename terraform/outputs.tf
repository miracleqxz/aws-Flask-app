output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "environment" {
  description = "Environment"
  value       = var.environment
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public_subnets[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private_subnets[*].id
}

output "frontend_instance_id" {
  description = "Frontend EC2 instance ID"
  value       = aws_instance.frontend.id
}

output "frontend_public_ip" {
  description = "Frontend public IP"
  value       = aws_instance.frontend.public_ip
}

output "frontend_private_ip" {
  description = "Frontend private IP"
  value       = aws_instance.frontend.private_ip
}

output "backend_instance_id" {
  description = "Backend EC2 instance ID"
  value       = aws_instance.backend.id
}

output "backend_private_ip" {
  description = "Backend private IP"
  value       = aws_instance.backend.private_ip
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL address (without port)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}

output "s3_bucket_name" {
  description = "S3 bucket name for movie posters"
  value       = aws_s3_bucket.posters.id
}

output "s3_bucket_url" {
  description = "S3 bucket URL"
  value       = "https://${aws_s3_bucket.posters.bucket_regional_domain_name}"
}

output "sqs_queue_url" {
  description = "SQS queue URL"
  value       = aws_sqs_queue.analytics.url
}

output "sqs_queue_arn" {
  description = "SQS queue ARN"
  value       = aws_sqs_queue.analytics.arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "frontend_service_name" {
  description = "Frontend ECS service name"
  value       = aws_ecs_service.frontend.name
}

output "backend_service_name" {
  description = "Backend ECS service name"
  value       = aws_ecs_service.backend.name
}

output "lambda_function_name" {
  description = "Lambda function name for backend control"
  value       = aws_lambda_function.backend_control.function_name
}

output "api_gateway_url" {
  description = "API Gateway base URL"
  value       = aws_apigatewayv2_api.backend_control.api_endpoint
}

output "api_endpoints" {
  description = "API endpoints for backend control"
  value = {
    start     = "${aws_apigatewayv2_api.backend_control.api_endpoint}/start"
    stop      = "${aws_apigatewayv2_api.backend_control.api_endpoint}/stop"
    heartbeat = "${aws_apigatewayv2_api.backend_control.api_endpoint}/heartbeat"
    status    = "${aws_apigatewayv2_api.backend_control.api_endpoint}/status"
  }
}

output "application_url" {
  description = "Main application URL"
  value       = "http://${aws_instance.frontend.public_ip}"
}

output "flask_direct_url" {
  description = "Flask direct access URL (for debugging)"
  value       = "http://${aws_instance.frontend.public_ip}:5000"
}

output "grafana_url" {
  description = "Grafana URL (when backend is running)"
  value       = "http://${aws_instance.backend.private_ip}:3000"
}

output "ecs_task_role_arn" {
  description = "ECS task role ARN"
  value       = aws_iam_role.ecs_task_role.arn
}

output "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "ecs_instance_profile_name" {
  description = "ECS instance profile name"
  value       = aws_iam_instance_profile.ecs_instance_profile.name
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log group names"
  value = {
    frontend = aws_cloudwatch_log_group.ecs_frontend.name
    backend  = aws_cloudwatch_log_group.ecs_backend.name
    lambda   = aws_cloudwatch_log_group.lambda.name
  }
}

output "connection_info" {
  description = "Connection information for setup scripts"
  sensitive   = true
  value = {
    postgres = {
      host     = aws_db_instance.postgres.address
      port     = aws_db_instance.postgres.port
      database = var.db_name
      username = var.db_username
      password = var.db_password
    }
    s3 = {
      bucket = aws_s3_bucket.posters.id
      region = var.aws_region
    }
    sqs = {
      queue_url = aws_sqs_queue.analytics.url
    }
  }
}

output "POSTGRES_HOST" {
  description = "PostgreSQL host for external tooling"
  value       = local.POSTGRES_HOST
}

output "POSTGRES_PORT" {
  description = "PostgreSQL port for external tooling"
  value       = local.POSTGRES_PORT
}

output "POSTGRES_DB" {
  description = "PostgreSQL database name for external tooling"
  value       = local.POSTGRES_DB
}

output "POSTGRES_USER" {
  description = "PostgreSQL user for external tooling"
  value       = local.POSTGRES_USER
}

output "POSTGRES_PASSWORD" {
  description = "PostgreSQL password for external tooling"
  value       = local.POSTGRES_PASSWORD
  sensitive   = true
}

output "MEILISEARCH_HOST" {
  description = "Meilisearch host for external tooling"
  value       = local.MEILISEARCH_HOST
}

output "MEILISEARCH_PORT" {
  description = "Meilisearch port for external tooling"
  value       = local.MEILISEARCH_PORT
}

output "data_pipeline_lambda_arn" {
  description = "ARN of the data pipeline Lambda function"
  value       = aws_lambda_function.data_pipeline.arn
}

output "data_pipeline_lambda_name" {
  description = "Name of the data pipeline Lambda function"
  value       = aws_lambda_function.data_pipeline.function_name
}


output "s3_movies_upload_path" {
  description = "S3 path for uploading movies.json"
  value       = "s3://${aws_s3_bucket.posters.id}/data/movies.json"
}

output "s3_posters_upload_path" {
  description = "S3 path for uploading posters"
  value       = "s3://${aws_s3_bucket.posters.id}/posters/"
}

output "ai_agent_instance_id" {
  description = "AI Agent EC2 instance ID"
  value       = aws_instance.ai_agent.id
}

output "ai_agent_public_ip" {
  description = "AI Agent EC2 instance public IP"
  value       = aws_instance.ai_agent.public_ip
}

output "ai_agent_private_ip" {
  description = "AI Agent EC2 instance private IP"
  value       = aws_instance.ai_agent.private_ip
}

output "ai_agent_api_gateway_url" {
  description = "AI Agent API Gateway URL"
  value       = aws_apigatewayv2_api.ai_agent_control.api_endpoint
}

output "ai_agent_lambda_function_name" {
  description = "AI Agent Lambda function name"
  value       = aws_lambda_function.ai_agent_control.function_name
}

output "ai_chat_api_gateway_url" {
  description = "AI Chat API Gateway URL"
  value       = aws_apigatewayv2_api.ai_chat.api_endpoint
  sensitive   = false
}

output "ai_chat_api_key" {
  description = "AI Chat API Key"
  value       = var.ai_chat_api_key
  sensitive   = true
}

