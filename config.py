import os


class Config:
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', '5000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    

    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    

    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'service-checker-db.xxxxx.us-east-1.rds.amazonaws.com')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'movies')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'your-password')
    

    REDIS_HOST = os.getenv('REDIS_HOST', 'redis.service.consul')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    

    SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789/service-checker-tasks')
    

    MEILISEARCH_HOST = os.getenv('MEILISEARCH_HOST', 'meilisearch.service.consul')
    MEILISEARCH_PORT = int(os.getenv('MEILISEARCH_PORT', '7700'))
    MEILISEARCH_KEY = os.getenv('MEILISEARCH_KEY', '')
    
  
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'service-checker-movie-posters')
    

    CONSUL_HOST = os.getenv('CONSUL_HOST', 'consul.service.consul')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    
  
    PROMETHEUS_HOST = os.getenv('PROMETHEUS_HOST', 'prometheus.service.consul')
    PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '9090'))
    
  
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')