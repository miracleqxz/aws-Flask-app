data "aws_ami" "ecs_optimized" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = file(var.ssh_public_key_path)

  tags = {
    Name = "${var.project_name}-key"
  }
}

resource "aws_instance" "frontend" {
  ami                    = data.aws_ami.ecs_optimized.id
  instance_type          = var.frontend_instance_type
  key_name               = aws_key_pair.main.key_name
  subnet_id              = aws_subnet.public_subnets[0].id
  vpc_security_group_ids = [aws_security_group.frontend.id]
  iam_instance_profile   = aws_iam_instance_profile.ecs_instance_profile.name


  # ECS Agent configuration
  user_data_base64 = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${var.ecs_cluster_name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_TASK_IAM_ROLE=true" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true" >> /etc/ecs/ecs.config
    
    # Tag instance for identification
    echo "ECS_INSTANCE_ATTRIBUTES={\"role\": \"frontend\"}" >> /etc/ecs/ecs.config
  EOF
  )

  root_block_device {
    volume_type           = "gp2"
    volume_size           = 30 # ECS-optimized AMI snapshot requires >= 30GB
    delete_on_termination = true
    encrypted             = true
  }

  monitoring = false

  tags = {
    Name        = "${var.project_name}-frontend"
    Project     = var.project_name
    Environment = var.environment
    Role        = "frontend"
  }

  lifecycle {
    ignore_changes = [ami]
  }
}


resource "aws_instance" "backend" {
  ami                    = data.aws_ami.ecs_optimized.id
  instance_type          = var.backend_instance_type
  key_name               = aws_key_pair.main.key_name
  subnet_id              = aws_subnet.public_subnets[1].id
  vpc_security_group_ids = [aws_security_group.backend.id]
  iam_instance_profile   = aws_iam_instance_profile.ecs_instance_profile.name

  # ECS Agent configuration
  user_data_base64 = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${var.ecs_cluster_name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_TASK_IAM_ROLE=true" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true" >> /etc/ecs/ecs.config
    
    # Tag instance for identification
    echo "ECS_INSTANCE_ATTRIBUTES={\"role\": \"backend\"}" >> /etc/ecs/ecs.config
  EOF
  )


  root_block_device {
    volume_type           = "gp2"
    volume_size           = 30 # ECS-optimized AMI snapshot requires >= 30GB
    delete_on_termination = true
    encrypted             = true
  }

  monitoring = false

  tags = {
    Name        = "${var.project_name}-backend"
    Project     = var.project_name
    Environment = var.environment
    Role        = "backend"
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_instance" "ai_agent" {
  ami                    = data.aws_ami.ecs_optimized.id
  instance_type          = var.ai_agent_instance_type
  key_name               = aws_key_pair.main.key_name
  subnet_id              = aws_subnet.public_subnets[0].id
  vpc_security_group_ids = [aws_security_group.ai_agent.id]
  iam_instance_profile   = aws_iam_instance_profile.ecs_instance_profile.name

  user_data_base64 = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${var.ecs_cluster_name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_TASK_IAM_ROLE=true" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true" >> /etc/ecs/ecs.config
    echo "ECS_INSTANCE_ATTRIBUTES={\"role\": \"ai-agent\"}" >> /etc/ecs/ecs.config
  EOF
  )

  root_block_device {
    volume_type           = "gp2"
    volume_size           = 30 # cannot shrink EBS; keep >= existing size
    delete_on_termination = true
    encrypted             = true
  }

  monitoring = false

  tags = {
    Name        = "${var.project_name}-ai-agent"
    Project     = var.project_name
    Environment = var.environment
    Role        = "ai-agent"
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

