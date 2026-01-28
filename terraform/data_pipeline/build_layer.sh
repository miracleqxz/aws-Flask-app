#!/bin/bash
set -e

LAYER_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${LAYER_DIR}/layer"

if [ -d "${OUTPUT_DIR}" ]; then
    sudo rm -rf "${OUTPUT_DIR}"
fi

mkdir -p "${OUTPUT_DIR}/python"

echo "Building psycopg2 layer for Lambda (Python 3.12)..."

docker run --rm \
    -v "${OUTPUT_DIR}/python:/output" \
    --user "$(id -u):$(id -g)" \
    --entrypoint /bin/bash \
    public.ecr.aws/lambda/python:3.12 \
    -c "pip install psycopg2-binary requests -t /output --no-cache-dir"

find "${OUTPUT_DIR}/python" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT_DIR}/python" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT_DIR}/python" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT_DIR}/python" -name "*.pyc" -delete 2>/dev/null || true

echo "Creating layer zip..."
cd "${OUTPUT_DIR}"
zip -r9 "${LAYER_DIR}/psycopg2_layer.zip" python

LAYER_SIZE=$(du -h "${LAYER_DIR}/psycopg2_layer.zip" | cut -f1)
echo "Layer built successfully: psycopg2_layer.zip (${LAYER_SIZE})"