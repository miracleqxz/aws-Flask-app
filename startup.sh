#!/bin/bash
set -e
echo ""
echo "Service Checker Startup"
echo ""
echo "Environment:"
echo "  PostgreSQL: ${POSTGRES_HOST}"
echo "  S3 Bucket: ${S3_BUCKET_NAME}"
echo "  Meilisearch: ${MEILISEARCH_HOST:-10.0.2.242}:${MEILISEARCH_PORT:-7700}"
echo ""

# Initialize database and S3
python3 /app/init_data.py || echo "Data initialization failed, continuing..."

# Index movies to Meilisearch (only if available)
echo ""
echo "Checking Meilisearch..."
MEILI_HOST="${MEILISEARCH_HOST:-10.0.2.242}"
MEILI_PORT="${MEILISEARCH_PORT:-7700}"

if curl -s --connect-timeout 5 "http://${MEILI_HOST}:${MEILI_PORT}/health" > /dev/null 2>&1; then
    echo "Meilisearch available, indexing movies..."
    python3 /app/index_movies_to_meilisearch.py || echo "Meilisearch indexing failed, continuing..."
else
    echo "Meilisearch not accessible, skipping indexing"
fi

echo ""
echo "Starting Flask Application"
echo ""
exec python3 /app/app.py
