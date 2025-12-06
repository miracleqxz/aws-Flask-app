#!/bin/bash
set -e

echo ""
echo "Service Checker Startup"
echo ""

echo "Environment:"
echo "  PostgreSQL: ${POSTGRES_HOST}"
echo "  S3 Bucket: ${S3_BUCKET_NAME}"
echo ""

wait_for_postgres() {
    echo "Waiting for PostgreSQL..."
    
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        sslmode='require',
        connect_timeout=5
    )
    conn.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
            echo "PostgreSQL ready"
            return 0
        fi
        
        attempt=$((attempt + 1))
        echo "  Attempt $attempt/$max_attempts..."
        sleep 2
    done
    
    echo "PostgreSQL connection timeout"
    return 1
}

wait_for_postgres || exit 1

echo ""
python3 /app/init_data.py

echo ""
echo "Starting Flask Application"
echo ""

exec python3 /app/app.py