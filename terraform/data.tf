resource "random_id" "suffix" {
  byte_length = 4
}


resource "aws_db_subnet_group" "main" {
  name        = "${var.project_name}-db-subnet-group"
  description = "Subnet group for RDS PostgreSQL"
  subnet_ids  = aws_subnet.private_subnets[*].id

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}


resource "aws_db_parameter_group" "postgres" {
  name        = "${var.project_name}-postgres-params"
  family      = "postgres15"
  description = "Custom parameter group for PostgreSQL"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  # Timezone
  parameter {
    name  = "timezone"
    value = "UTC"
  }

  tags = {
    Name = "${var.project_name}-postgres-params"
  }
}


resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-db"


  engine               = "postgres"
  engine_version       = var.db_engine_version
  instance_class       = var.db_instance_class
  parameter_group_name = aws_db_parameter_group.postgres.name


  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp2"
  storage_encrypted     = true


  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = var.db_port


  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = var.db_publicly_accessible
  multi_az               = false


  backup_retention_period = var.environment == "prod" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"


  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${var.project_name}-final-snapshot-${random_id.suffix.hex}"


  performance_insights_enabled          = true
  performance_insights_retention_period = 7


  monitoring_interval = 0

  tags = {
    Name        = "${var.project_name}-postgres"
    Project     = var.project_name
    Environment = var.environment
  }

  lifecycle {
    prevent_destroy = false
  }
}


locals {
  s3_bucket_name = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project_name}-posters-${random_id.suffix.hex}"

  POSTGRES_HOST     = aws_db_instance.postgres.address
  POSTGRES_PORT     = aws_db_instance.postgres.port
  POSTGRES_DB       = var.db_name
  POSTGRES_USER     = var.db_username
  POSTGRES_PASSWORD = var.db_password

  MEILISEARCH_HOST = aws_instance.backend.private_ip
  MEILISEARCH_PORT = 7700
}

resource "aws_s3_bucket" "posters" {
  bucket        = local.s3_bucket_name
  force_destroy = var.s3_force_destroy

  tags = {
    Name        = local.s3_bucket_name
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "posters" {
  bucket = aws_s3_bucket.posters.id

  versioning_configuration {
    status = var.environment == "prod" ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_public_access_block" "posters" {
  bucket = aws_s3_bucket.posters.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}


resource "aws_s3_bucket_policy" "posters_public_read" {
  bucket = aws_s3_bucket.posters.id


  depends_on = [aws_s3_bucket_public_access_block.posters]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.posters.arn}/*"
      }
    ]
  })
}


resource "aws_s3_bucket_cors_configuration" "posters" {
  bucket = aws_s3_bucket.posters.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"] # Restrict to your domain in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}


resource "aws_s3_bucket_lifecycle_configuration" "posters" {
  bucket = aws_s3_bucket.posters.id

  rule {
    id     = "cleanup-incomplete-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}


resource "aws_sqs_queue" "analytics" {
  name = var.sqs_queue_name

  # Message settings
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  max_message_size           = 262144 # 256 KB
  delay_seconds              = 0
  receive_wait_time_seconds  = 10


  # Encryption
  sqs_managed_sse_enabled = true

  tags = {
    Name        = var.sqs_queue_name
    Project     = var.project_name
    Environment = var.environment
  }
}

# SQS Queue Policy - Allow ECS tasks to send/receive
resource "aws_sqs_queue_policy" "analytics" {
  queue_url = aws_sqs_queue.analytics.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSTaskAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task_role.arn
        }
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.analytics.arn
      }
    ]
  })
}


resource "aws_dynamodb_table" "backend_state" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST" # No provisioned capacity needed
  hash_key     = "key"

  attribute {
    name = "key"
    type = "S"
  }

  # TTL for auto-cleanup (optional)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = var.dynamodb_table_name
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_data_pipeline" {
  name              = "/aws/lambda/${var.project_name}-data-pipeline"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-data-pipeline-logs"
      Project     = var.project_name
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_log_group" "ecs_frontend" {
  name              = "/ecs/${var.project_name}-frontend"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-frontend-logs"
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "ecs_backend" {
  name              = "/ecs/${var.project_name}-backend"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-backend-logs"
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-lambda-logs"
    Project     = var.project_name
    Environment = var.environment
  }
}

# S3 Event Notification

resource "aws_lambda_permission" "s3_data_pipeline" {
  statement_id   = "AllowS3Invoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.data_pipeline.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.posters.arn
  source_account = data.aws_caller_identity.current.account_id
}

resource "aws_s3_bucket_notification" "movies_upload" {
  bucket = aws_s3_bucket.posters.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.data_pipeline.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "data/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.s3_data_pipeline]
}
