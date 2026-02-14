import os


class Config:
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')  # nosec B104 - Required for container/EC2 deployment
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'movies')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

    SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL', '')

    MEILISEARCH_HOST = os.getenv('MEILISEARCH_HOST', 'localhost')
    MEILISEARCH_PORT = int(os.getenv('MEILISEARCH_PORT', '7700'))
    MEILISEARCH_KEY = os.getenv('MEILISEARCH_KEY', None)

    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'service-checker-movie-posters')

    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))

    NGINX_HOST = os.getenv('NGINX_HOST', 'localhost')
    NGINX_PORT = int(os.getenv('NGINX_PORT', '80'))

    VICTORIAMETRICS_HOST = os.getenv('VICTORIAMETRICS_HOST', 'localhost')
    VICTORIAMETRICS_PORT = int(os.getenv('VICTORIAMETRICS_PORT', '8428'))

    GRAFANA_HOST = os.getenv('GRAFANA_HOST', 'localhost')
    GRAFANA_PORT = int(os.getenv('GRAFANA_PORT', '3000'))

    LAMBDA_AI_AGENT_CONTROL = os.getenv('LAMBDA_AI_AGENT_CONTROL', 'ai-agent-control')
    LAMBDA_SCHEDULER = os.getenv('LAMBDA_SCHEDULER', 'Flask_project-instance-scheduler')

    LAMBDA_DATA_PIPELINE = os.getenv('LAMBDA_DATA_PIPELINE', 'Flask_project-data-pipeline')

    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
