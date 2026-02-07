variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile to use (optional)"
  type        = string
  default     = null
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "Flask_project"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "common_tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default     = {}
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (minimum 2 for RDS)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (for RDS)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}


variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "frontend_instance_type" {
  description = "EC2 instance type for frontend (flask-app + nginx)"
  type        = string
  default     = "t2.micro"
}

#variable "frontend_key_name" {
# description = "SSH key pair name for frontend EC2"
#type        = string
#}

variable "frontend_associate_public_ip" {
  description = "Associate public IP with frontend instance"
  type        = bool
  default     = true
}

variable "backend_instance_type" {
  description = "EC2 instance type for backend (redis, meilisearch, monitoring)"
  type        = string
  default     = "t3.small"
}

variable "ai_agent_instance_type" {
  description = "EC2 instance type for AI agent"
  type        = string
  default     = "t3.small"
}

#variable "backend_key_name" {
# description = "SSH key pair name for backend EC2 (can be same as frontend)"
# type        = string
#}

variable "ssh_public_key_path" {
  description = "Path to SSH public key file"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "movies"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8
    error_message = "Database password must be at least 8 characters."
  }
}

variable "db_port" {
  description = "PostgreSQL port"
  type        = number
  default     = 5432
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum storage for autoscaling (0 to disable)"
  type        = number
  default     = 0
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot when destroying RDS"
  type        = bool
  default     = true # true for dev, false for prod
}

variable "db_publicly_accessible" {
  description = "Make RDS publicly accessible (for Ansible init)"
  type        = bool
  default     = false
}

variable "s3_bucket_name" {
  description = "S3 bucket name for movie posters (must be globally unique)"
  type        = string
  default     = ""

  validation {
    condition     = var.s3_bucket_name == "" || can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.s3_bucket_name))
    error_message = "S3 bucket name must be valid (lowercase, 3-63 chars, no underscores)."
  }
}

variable "s3_force_destroy" {
  description = "Force destroy S3 bucket even if not empty"
  type        = bool
  default     = true # true for dev, false for prod
}

variable "sqs_queue_name" {
  description = "SQS queue name for analytics events"
  type        = string
  default     = "service-checker-tasks"
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds"
  type        = number
  default     = 30
}

variable "sqs_message_retention" {
  description = "SQS message retention period in seconds"
  type        = number
  default     = 86400 # 1 day
}

variable "ecs_cluster_name" {
  description = "ECS cluster name"
  type        = string
  default     = "service-checker-cluster"
}

# Frontend Task
variable "frontend_task_cpu" {
  description = "CPU units for frontend task (flask-app + nginx)"
  type        = number
  default     = 512 # 0.5 vCPU
}

variable "frontend_task_memory" {
  description = "Memory (MB) for frontend task"
  type        = number
  default     = 768 # Leave ~256MB for OS
}

# Backend Task
variable "backend_task_cpu" {
  description = "CPU units for backend task (all services)"
  type        = number
  default     = 1536 # 1.5 vCPU
}

variable "backend_task_memory" {
  description = "Memory (MB) for backend task"
  type        = number
  default     = 1792 # ~1.75GB for all backend services
}

variable "flask_app_image" {
  description = "Docker image for flask-app"
  type        = string
  default     = "ghcr.io/miracleqxz/k8s-flask-app:aws"
}

variable "nginx_image" {
  description = "Docker image for nginx"
  type        = string
  default     = "ghcr.io/miracleqxz/service-checker-nginx:latest"
}

variable "redis_image" {
  description = "Docker image for redis"
  type        = string
  default     = "redis:7-alpine"
}

variable "meilisearch_image" {
  description = "Docker image for meilisearch"
  type        = string
  default     = "getmeili/meilisearch:latest"
}

variable "consul_image" {
  description = "Docker image for consul"
  type        = string
  default     = "hashicorp/consul:latest"
}

variable "prometheus_image" {
  description = "Docker image for prometheus"
  type        = string
  default     = "prom/prometheus:latest"
}

variable "grafana_image" {
  description = "Docker image for grafana"
  type        = string
  default     = "grafana/grafana:latest"
}

variable "lambda_function_name" {
  description = "Lambda function name for backend control"
  type        = string
  default     = "backend-control"
}

variable "lambda_ai_agent_function_name" {
  description = "Lambda function name for AI agent control"
  type        = string
  default     = "ai-agent-control"
}

variable "lambda_ai_chat_proxy_function_name" {
  description = "Lambda function name for AI chat proxy"
  type        = string
  default     = "ai-chat-proxy"
}

variable "ai_chat_api_key" {
  description = "API key for AI chat endpoints"
  type        = string
  default     = ""
  sensitive   = true
}

variable "ai_chat_max_requests" {
  description = "Maximum requests per user per window for AI chat"
  type        = number
  default     = 10
}

variable "ai_chat_window_seconds" {
  description = "Time window in seconds for AI chat rate limiting"
  type        = number
  default     = 60
}

variable "ai_chat_idle_timeout_minutes" {
  description = "Minutes of inactivity before shutting down AI agent instance"
  type        = number
  default     = 5
}

variable "heartbeat_timeout_minutes" {
  description = "Minutes without heartbeat before stopping backend"
  type        = number
  default     = 5

  validation {
    condition     = var.heartbeat_timeout_minutes >= 1 && var.heartbeat_timeout_minutes <= 60
    error_message = "Heartbeat timeout must be between 1 and 60 minutes."
  }
}

variable "heartbeat_interval_seconds" {
  description = "Interval between heartbeat checks (EventBridge)"
  type        = number
  default     = 60 # Check every minute
}

variable "dynamodb_table_name" {
  description = "DynamoDB table for backend state"
  type        = string
  default     = "backend-state"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7 # Short for dev 

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention period."
  }
}

variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

variable "create_ssl_certificate" {
  description = "Create ACM SSL certificate for domain"
  type        = bool
  default     = false
}


variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH into EC2 instances"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "allowed_http_cidrs" {
  description = "CIDR blocks allowed to access HTTP/HTTPS"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}


variable "meilisearch_master_key" {
  description = "Meilisearch master key (optional, for security)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "meilisearch_port" {
  description = "Meilisearch port"
  type        = string
  default     = "7700"
}

variable "lambda_data_pipeline_name" {
  description = "Lambda function name for data pipeline"
  type        = string
  default     = "data-pipeline"
}


variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "ai_agent_image" {
  description = "Docker image for AI agent (ECS)"
  type        = string
  default     = "ghcr.io/miracleqxz/k8s-flask-app:ai-agent"
}

variable "cursor_api_key" {
  description = "API key for Cursor/OpenAI-compatible API (AI chat)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cursor_api_base_url" {
  description = "Base URL for Cursor/OpenAI-compatible API"
  type        = string
  default     = ""
}

variable "cursor_model" {
  description = "Model name for Cursor/OpenAI API"
  type        = string
  default     = ""
}
