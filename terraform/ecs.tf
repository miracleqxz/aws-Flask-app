resource "aws_ecs_cluster" "main" {
  name = var.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name        = var.ecs_cluster_name
    Project     = var.project_name
    Environment = var.environment
  }
}


resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  network_mode             = "host"
  requires_compatibilities = ["EC2"]
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn


  cpu    = var.frontend_task_cpu
  memory = var.frontend_task_memory

  container_definitions = jsonencode([
    {
      name              = "flask-app"
      image             = var.flask_app_image
      essential         = true
      cpu               = 384
      memory            = 512
      memoryReservation = 256

      #portMappings = [
      # {
      #   containerPort = 5000
      #   hostPort      = 5000
      #  protocol      = "tcp"
      #}
      #]

      environment = [
        { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
        { name = "POSTGRES_PORT", value = tostring(aws_db_instance.postgres.port) },
        { name = "POSTGRES_DB", value = var.db_name },
        { name = "POSTGRES_USER", value = var.db_username },
        { name = "POSTGRES_PASSWORD", value = var.db_password },

        { name = "REDIS_HOST", value = aws_instance.backend.private_ip },
        { name = "REDIS_PORT", value = "6379" },
        { name = "MEILISEARCH_HOST", value = aws_instance.backend.private_ip },
        { name = "MEILISEARCH_PORT", value = "7700" },
        { name = "MEILISEARCH_KEY", value = var.meilisearch_master_key },

        { name = "CONSUL_HOST", value = aws_instance.backend.private_ip },
        { name = "CONSUL_PORT", value = "8500" },
        { name = "PROMETHEUS_HOST", value = aws_instance.backend.private_ip },
        { name = "PROMETHEUS_PORT", value = "9090" },
        { name = "GRAFANA_HOST", value = aws_instance.backend.private_ip },
        { name = "GRAFANA_PORT", value = "3000" },
        { name = "NGINX_HOST", value = "127.0.0.1" },
        { name = "NGINX_PORT", value = "80" },

        { name = "AWS_REGION", value = var.aws_region },
        { name = "S3_BUCKET_NAME", value = aws_s3_bucket.posters.id },
        { name = "SQS_QUEUE_URL", value = aws_sqs_queue.analytics.url },

        { name = "LAMBDA_BACKEND_CONTROL", value = var.lambda_function_name },

        { name = "AI_CHAT_API_URL", value = aws_apigatewayv2_api.ai_chat.api_endpoint },
        { name = "AI_CHAT_API_KEY", value = var.ai_chat_api_key },

        { name = "FLASK_HOST", value = "0.0.0.0" },
        { name = "FLASK_PORT", value = "5000" },
        { name = "PYTHONUNBUFFERED", value = "1" }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_frontend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "flask-app"
        }
      }
    },

    {
      name              = "nginx"
      image             = var.nginx_image
      essential         = true
      cpu               = 128
      memory            = 128
      memoryReservation = 64

      #portMappings = [
      #  {
      #    containerPort = 80
      #    hostPort      = 80
      #    protocol      = "tcp"
      #  }
      #]


      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost/ || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_frontend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "nginx"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-frontend-task"
    Project     = var.project_name
    Environment = var.environment
  }
}


resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  network_mode             = "host"
  requires_compatibilities = ["EC2"]
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  cpu    = var.backend_task_cpu
  memory = var.backend_task_memory

  container_definitions = jsonencode([
    {
      name              = "redis"
      image             = var.redis_image
      essential         = true
      cpu               = 128
      memory            = 256
      memoryReservation = 128

      portMappings = [
        {
          containerPort = 6379
          hostPort      = 6379
          protocol      = "tcp"
        }
      ]

      healthCheck = {
        command     = ["CMD", "redis-cli", "ping"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 10
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "redis"
        }
      }
    },

    {
      name              = "meilisearch"
      image             = var.meilisearch_image
      essential         = true
      cpu               = 256
      memory            = 512
      memoryReservation = 256

      portMappings = [
        {
          containerPort = 7700
          hostPort      = 7700
          protocol      = "tcp"
        }
      ]

      environment = var.meilisearch_master_key != "" ? [
        { name = "MEILI_MASTER_KEY", value = var.meilisearch_master_key }
      ] : []

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:7700/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "meilisearch"
        }
      }
    },

    {
      name              = "prometheus"
      image             = var.prometheus_image
      essential         = false
      cpu               = 128
      memory            = 256
      memoryReservation = 128

      portMappings = [
        {
          containerPort = 9090
          hostPort      = 9090
          protocol      = "tcp"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget -q --spider http://localhost:9090/-/healthy || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "prometheus"
        }
      }
    },

    {
      name              = "grafana"
      image             = var.grafana_image
      essential         = false
      cpu               = 128
      memory            = 256
      memoryReservation = 128

      portMappings = [
        {
          containerPort = 3000
          hostPort      = 3000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "GF_SECURITY_ADMIN_PASSWORD", value = var.grafana_admin_password }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:3000/api/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "grafana"
        }
      }
    },

    {
      name              = "analytics-worker"
      image             = var.flask_app_image
      essential         = false
      cpu               = 128
      memory            = 256
      memoryReservation = 128

      command = ["python", "analytics_worker.py"]

      environment = [
        { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
        { name = "POSTGRES_PORT", value = tostring(aws_db_instance.postgres.port) },
        { name = "POSTGRES_DB", value = var.db_name },
        { name = "POSTGRES_USER", value = var.db_username },
        { name = "POSTGRES_PASSWORD", value = var.db_password },

        { name = "REDIS_HOST", value = "172.17.0.1" },
        { name = "REDIS_PORT", value = "6379" },

        { name = "AWS_REGION", value = var.aws_region },
        { name = "SQS_QUEUE_URL", value = aws_sqs_queue.analytics.url },

        { name = "PYTHONUNBUFFERED", value = "1" }
      ]

      dependsOn = [
        {
          containerName = "redis"
          condition     = "HEALTHY"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "analytics-worker"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-backend-task"
    Project     = var.project_name
    Environment = var.environment
  }
}


resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "EC2"


  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  placement_constraints {
    type       = "memberOf"
    expression = "attribute:role == frontend"
  }

  wait_for_steady_state = false

  tags = {
    Name        = "${var.project_name}-frontend-service"
    Project     = var.project_name
    Environment = var.environment
  }

  depends_on = [
    aws_instance.frontend,
    aws_db_instance.postgres
  ]
}


resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "EC2"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  placement_constraints {
    type       = "memberOf"
    expression = "attribute:role == backend"
  }

  wait_for_steady_state = false

  tags = {
    Name        = "${var.project_name}-backend-service"
    Project     = var.project_name
    Environment = var.environment
  }

  depends_on = [
    aws_instance.backend
  ]
}
