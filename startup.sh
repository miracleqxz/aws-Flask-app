#!/bin/bash
set -e

echo ""
echo "Service Checker Startup"
echo ""

echo "Environment:"
echo "  PostgreSQL: ${POSTGRES_HOST}"
echo "  S3 Bucket: ${S3_BUCKET_NAME}"
echo ""


python3 /app/init_data.py || echo "Data initialization failed, continuing..."

echo ""
echo "Starting Flask Application"
echo ""

exec python3 /app/app.py