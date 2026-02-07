resource "aws_lambda_layer_version" "psycopg2" {
  filename            = "${path.module}/data_pipeline/psycopg2_layer.zip"
  layer_name          = "${var.project_name}-psycopg2"
  compatible_runtimes = ["python3.12"]
  description         = "psycopg2-binary and requests for data pipeline"

  source_code_hash = filebase64sha256("${path.module}/data_pipeline/psycopg2_layer.zip")
}


# Lambda Function - Data Pipeline


data "archive_file" "lambda_data_pipeline" {
  type        = "zip"
  output_path = "${path.module}/lambda_data_pipeline.zip"

  source {
    content  = <<-PYTHON
import json
import os
import logging
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import boto3
import psycopg2
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
S3_BUCKET = os.environ['S3_BUCKET_NAME']
MOVIES_KEY = os.environ.get('MOVIES_S3_KEY', 'data/movies.json')
POSTERS_PREFIX = os.environ.get('POSTERS_S3_PREFIX', 'posters/')

PG_HOST = os.environ['POSTGRES_HOST']
PG_PORT = os.environ.get('POSTGRES_PORT', '5432')
PG_DB = os.environ['POSTGRES_DB']
PG_USER = os.environ['POSTGRES_USER']
PG_PASSWORD = os.environ['POSTGRES_PASSWORD']

MEILI_HOST = os.environ.get('MEILISEARCH_HOST', '')
MEILI_PORT = os.environ.get('MEILISEARCH_PORT', '7700')

s3 = boto3.client('s3')


# Database Functions


def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        sslmode='require',
        connect_timeout=10
    )


def ensure_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            year INTEGER NOT NULL,
            rating DECIMAL(3, 1) NOT NULL,
            genre VARCHAR(255) NOT NULL,
            director VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            poster_filename VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_queries (
            id SERIAL PRIMARY KEY,
            query VARCHAR(255) NOT NULL,
            results_count INTEGER NOT NULL,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


def sync_movies_to_postgres(movies):
    logger.info(f"Syncing {len(movies)} movies to PostgreSQL")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        ensure_tables(cursor)
        
        values = [
            (
                m['id'], m['title'], m['year'], m['rating'],
                m['genre'], m['director'], m['description'], m['poster_filename']
            )
            for m in movies
        ]
        
        cursor.executemany("""
            INSERT INTO movies (id, title, year, rating, genre, director, description, poster_filename)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                year = EXCLUDED.year,
                rating = EXCLUDED.rating,
                genre = EXCLUDED.genre,
                director = EXCLUDED.director,
                description = EXCLUDED.description,
                poster_filename = EXCLUDED.poster_filename;
        """, values)
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM movies;")
        total = cursor.fetchone()[0]
        
        logger.info(f"PostgreSQL sync complete: {total} movies total")
        return {'status': 'ok', 'synced': len(movies), 'total': total}
        
    finally:
        cursor.close()
        conn.close()


def get_movies_from_postgres():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, title, description, poster_filename, year, rating, genre, director
            FROM movies ORDER BY id;
        """)
        
        movies = []
        for row in cursor.fetchall():
            movies.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'poster_filename': row[3],
                'year': row[4],
                'rating': float(row[5]),
                'genre': row[6],
                'director': row[7]
            })
        
        return movies
        
    finally:
        cursor.close()
        conn.close()


# S3 Functions


def load_movies_from_s3():
    logger.info(f"Loading movies from s3://{S3_BUCKET}/{MOVIES_KEY}")
    
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=MOVIES_KEY)
        content = response['Body'].read().decode('utf-8')
        movies = json.loads(content)
        logger.info(f"Loaded {len(movies)} movies from S3")
        return movies
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.warning(f"Movies file not found: {MOVIES_KEY}")
            return None
        raise


# Meilisearch Functions (using urllib instead of requests)

def meili_request(method, path, data=None, timeout=10):
    if not MEILI_HOST:
        return None
    
    url = f"http://{MEILI_HOST}:{MEILI_PORT}{path}"
    
    headers = {'Content-Type': 'application/json'}
    body = json.dumps(data).encode('utf-8') if data else None
    
    req = Request(url, data=body, headers=headers, method=method)
    
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        if e.code == 404:
            return None
        logger.error(f"Meilisearch HTTP error: {e.code} {e.reason}")
        raise
    except URLError as e:
        logger.warning(f"Meilisearch not accessible: {e.reason}")
        return None


def check_meilisearch_health():
    result = meili_request('GET', '/health')
    return result is not None and result.get('status') == 'available'


def get_indexed_movie_ids():
    existing_ids = set()
    
    stats = meili_request('GET', '/indexes/movies/stats')
    if stats is None:
        return existing_ids, False
    
    limit = 1000
    offset = 0
    
    while True:
        result = meili_request('GET', f'/indexes/movies/documents?fields=id&limit={limit}&offset={offset}')
        if result is None:
            break
        
        docs = result.get('results', result) if isinstance(result, dict) else result
        if not docs:
            break
        
        for doc in docs:
            if 'id' in doc:
                existing_ids.add(doc['id'])
        
        if len(docs) < limit:
            break
        offset += limit
    
    return existing_ids, True


def reindex_meilisearch(movies):
    if not MEILI_HOST:
        logger.info("Meilisearch not configured, skipping")
        return {'status': 'skipped', 'reason': 'not_configured'}
    
    if not check_meilisearch_health():
        logger.warning("Meilisearch not accessible")
        return {'status': 'skipped', 'reason': 'not_accessible'}
    
    logger.info("Reindexing Meilisearch...")
    
    existing_ids, index_exists = get_indexed_movie_ids()
    
    if not index_exists:
        meili_request('POST', '/indexes', {'uid': 'movies', 'primaryKey': 'id'})
        meili_request('PUT', '/indexes/movies/settings/searchable-attributes',
                      ['title', 'description', 'director', 'genre'])
    
    missing_movies = [m for m in movies if m['id'] not in existing_ids]
    
    if not missing_movies:
        logger.info("Meilisearch index is up to date")
        return {'status': 'ok', 'indexed': 0, 'message': 'already_up_to_date'}
    
    logger.info(f"Indexing {len(missing_movies)} new movies")
    result = meili_request('POST', '/indexes/movies/documents', missing_movies, timeout=30)
    
    if result:
        return {'status': 'ok', 'indexed': len(missing_movies), 'task': result.get('taskUid')}
    
    return {'status': 'error', 'message': 'indexing_failed'}


# Pipeline Actions

def run_full_sync(force=False):
    results = {
        's3': {'status': 'pending'},
        'postgres': {'status': 'pending'},
        'meilisearch': {'status': 'pending'}
    }
    
    # Step 1: Load movies from S3
    movies = load_movies_from_s3()
    if movies is None:
        results['s3'] = {'status': 'error', 'message': 'movies.json not found'}
        return results
    
    results['s3'] = {'status': 'ok', 'movies_count': len(movies)}
    
    # Step 2: Sync to PostgreSQL
    try:
        results['postgres'] = sync_movies_to_postgres(movies)
    except Exception as e:
        logger.error(f"PostgreSQL sync failed: {e}")
        results['postgres'] = {'status': 'error', 'message': str(e)}
        return results
    
    # Step 3: Reindex Meilisearch (get fresh data from DB)
    try:
        db_movies = get_movies_from_postgres()
        results['meilisearch'] = reindex_meilisearch(db_movies)
    except Exception as e:
        logger.error(f"Meilisearch reindex failed: {e}")
        results['meilisearch'] = {'status': 'error', 'message': str(e)}
    
    return results


def get_pipeline_status():
    status = {
        's3': {'status': 'unknown'},
        'postgres': {'status': 'unknown'},
        'meilisearch': {'status': 'unknown'}
    }
    
    # Check S3
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=MOVIES_KEY)
        status['s3'] = {'status': 'ok', 'bucket': S3_BUCKET, 'key': MOVIES_KEY}
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            status['s3'] = {'status': 'missing', 'message': 'movies.json not found'}
        else:
            status['s3'] = {'status': 'error', 'message': str(e)}
    
    # Check PostgreSQL
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        status['postgres'] = {'status': 'ok', 'movies_count': count}
    except Exception as e:
        status['postgres'] = {'status': 'error', 'message': str(e)}
    
    # Check Meilisearch
    if MEILI_HOST:
        if check_meilisearch_health():
            stats = meili_request('GET', '/indexes/movies/stats')
            if stats:
                status['meilisearch'] = {
                    'status': 'ok',
                    'documents': stats.get('numberOfDocuments', 0)
                }
            else:
                status['meilisearch'] = {'status': 'ok', 'documents': 0, 'message': 'index not created'}
        else:
            status['meilisearch'] = {'status': 'unreachable'}
    else:
        status['meilisearch'] = {'status': 'not_configured'}
    
    return status

# Lambda Handler

def handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    
    action = 'sync'
    source = 'unknown'
    
    # Determine action from event source
    if 'Records' in event:
        # S3 Event
        source = 's3'
        record = event['Records'][0]
        if record.get('eventSource') == 'aws:s3':
            key = record['s3']['object']['key']
            logger.info(f"S3 event for key: {key}")
            
            if key == MOVIES_KEY or key.endswith('movies.json'):
                action = 'sync'
            else:
                logger.info(f"Ignoring S3 event for {key}")
                return {'statusCode': 200, 'body': json.dumps({'status': 'ignored', 'key': key})}
    
    elif 'requestContext' in event:
        # API Gateway (if added later)
        source = 'api'
        path = event.get('rawPath', event.get('path', ''))
        method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        
        if '/sync' in path and method == 'POST':
            action = 'sync'
        elif '/status' in path:
            action = 'status'
        else:
            action = 'status'
    
    elif event.get('source') == 'aws.events':
        # EventBridge scheduled event
        source = 'eventbridge'
        action = event.get('action', 'sync')
    
    else:
        # Direct invocation (from Flask via boto3)
        source = 'direct'
        action = event.get('action', 'sync')
    
    logger.info(f"Action: {action}, Source: {source}")
    
    try:
        if action == 'sync':
            result = run_full_sync()
        elif action == 'status':
            result = get_pipeline_status()
        else:
            result = {'error': f'Unknown action: {action}'}
        
        result['_meta'] = {'action': action, 'source': source}
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'message': str(e),
                '_meta': {'action': action, 'source': source}
            })
        }
PYTHON
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "data_pipeline" {
  function_name = "${var.project_name}-data-pipeline"
  role          = aws_iam_role.lambda_data_pipeline.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.12"
  timeout       = 120
  memory_size   = 256

  filename         = data.archive_file.lambda_data_pipeline.output_path
  source_code_hash = data.archive_file.lambda_data_pipeline.output_base64sha256

  layers = [aws_lambda_layer_version.psycopg2.arn]

  vpc_config {
    subnet_ids         = aws_subnet.private_subnets[*].id
    security_group_ids = [aws_security_group.lambda_data_pipeline.id]
  }

  environment {
    variables = {
      S3_BUCKET_NAME    = aws_s3_bucket.posters.id
      MOVIES_S3_KEY     = "data/movies.json"
      POSTERS_S3_PREFIX = "posters/"
      POSTGRES_HOST     = local.POSTGRES_HOST
      POSTGRES_PORT     = tostring(local.POSTGRES_PORT)
      POSTGRES_DB       = local.POSTGRES_DB
      POSTGRES_USER     = local.POSTGRES_USER
      POSTGRES_PASSWORD = local.POSTGRES_PASSWORD
      MEILISEARCH_HOST  = local.MEILISEARCH_HOST
      MEILISEARCH_PORT  = tostring(local.MEILISEARCH_PORT)
    }
  }

  tags = {
    Name        = "${var.project_name}-data-pipeline"
    Project     = var.project_name
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_data_pipeline,
    aws_iam_role_policy_attachment.lambda_data_pipeline_basic,
    aws_iam_role_policy_attachment.lambda_data_pipeline_vpc
  ]
}



