#!/bin/bash
set -e
echo "Service Checker Startup"
echo "  PostgreSQL: ${POSTGRES_HOST}"
echo "  S3 Bucket: ${S3_BUCKET_NAME}"
echo "  Meilisearch: ${MEILISEARCH_HOST:-10.0.2.242}:${MEILISEARCH_PORT:-7700}"

python3 /app/init_data.py || echo "Data initialization failed, continuing..."

MEILI_HOST="${MEILISEARCH_HOST:-10.0.2.242}"
MEILI_PORT="${MEILISEARCH_PORT:-7700}"
MEILI_URL="http://${MEILI_HOST}:${MEILI_PORT}"

echo "Waiting for Meilisearch at ${MEILI_URL}..."
for i in $(seq 1 30); do
    if curl -s --connect-timeout 3 "${MEILI_URL}/health" > /dev/null 2>&1; then
        echo "Meilisearch is ready (attempt $i)"
        echo "Indexing movies..."
        python3 -c "from database.meilisearch_sync import index_all_movies; index_all_movies()" || echo "Meilisearch indexing failed"
        break
    fi
    echo "  attempt $i/30 — not ready, waiting 5s..."
    sleep 5
done

exec python3 /app/app.py
