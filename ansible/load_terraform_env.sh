#!/bin/bash
set -e

TERRAFORM_DIR="${TERRAFORM_DIR:-../terraform}"

echo "Loading Terraform outputs from $TERRAFORM_DIR..."


if [ ! -d "$TERRAFORM_DIR" ]; then
    echo "ERROR: Terraform directory not found: $TERRAFORM_DIR"
    echo "Please set TERRAFORM_DIR or run from the correct location"
    exit 1
fi


cd "$TERRAFORM_DIR"

if ! terraform state list > /dev/null 2>&1; then
    echo "ERROR: No Terraform state found. Run 'terraform apply' first."
    exit 1
fi

echo "Extracting outputs..."


export AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")
export POSTGRES_HOST=$(terraform output -raw rds_address 2>/dev/null || echo "")
export POSTGRES_PORT=$(terraform output -raw rds_port 2>/dev/null || echo "5432")
export POSTGRES_DB=$(terraform output -raw rds_database_name 2>/dev/null || echo "movies")
export POSTGRES_USER="postgres"
# Note: Password must be set manually for security
export POSTGRES_PASSWORD="your-password-here"

export S3_BUCKET_NAME=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
export SQS_QUEUE_URL=$(terraform output -raw sqs_queue_url 2>/dev/null || echo "")

export FRONTEND_IP=$(terraform output -raw frontend_public_ip 2>/dev/null || echo "")
export BACKEND_IP=$(terraform output -raw backend_private_ip 2>/dev/null || echo "")
export BACKEND_INSTANCE_ID=$(terraform output -raw backend_instance_id 2>/dev/null || echo "")

export API_GATEWAY_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")
export LAMBDA_BACKEND_CONTROL=$(terraform output -raw lambda_function_name 2>/dev/null || echo "backend-control")

export ECS_CLUSTER_NAME=$(terraform output -raw ecs_cluster_name 2>/dev/null || echo "")
export FRONTEND_SERVICE=$(terraform output -raw frontend_service_name 2>/dev/null || echo "")
export BACKEND_SERVICE=$(terraform output -raw backend_service_name 2>/dev/null || echo "")

# Return to original directory
cd - > /dev/null

echo ""
echo "Environment variables loaded:"
echo "  AWS_REGION=$AWS_REGION"
echo "  POSTGRES_HOST=$POSTGRES_HOST"
echo "  POSTGRES_PORT=$POSTGRES_PORT"
echo "  POSTGRES_DB=$POSTGRES_DB"
echo "  S3_BUCKET_NAME=$S3_BUCKET_NAME"
echo "  SQS_QUEUE_URL=$SQS_QUEUE_URL"
echo "  FRONTEND_IP=$FRONTEND_IP"
echo "  BACKEND_IP=$BACKEND_IP"
echo "  API_GATEWAY_URL=$API_GATEWAY_URL"
echo ""
echo "NOTE: POSTGRES_PASSWORD must be set manually!"
echo ""
echo "Application URL: http://$FRONTEND_IP"
