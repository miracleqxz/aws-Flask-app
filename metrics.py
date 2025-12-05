from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response
import time
import functools


REQUEST_COUNT = Counter(
    'flask_request_count',
    'Total Flask Request Count',
    ['method', 'endpoint', 'http_status']
)

REQUEST_DURATION = Histogram(
    'flask_request_duration_seconds',
    'Flask Request Duration',
    ['method', 'endpoint']
)


DB_CONNECTION_COUNT = Gauge(
    'flask_db_connections',
    'Number of active database connections'
)


CACHE_HIT_COUNT = Counter(
    'flask_cache_hits_total',
    'Total cache hits'
)

CACHE_MISS_COUNT = Counter(
    'flask_cache_misses_total',
    'Total cache misses'
)


SEARCH_QUERY_COUNT = Counter(
    'flask_search_queries_total',
    'Total search queries'
)

SEARCH_RESULTS_COUNT = Histogram(
    'flask_search_results',
    'Number of search results returned'
)


MOVIE_VIEWS = Counter(
    'flask_movie_views_total',
    'Total movie page views',
    ['movie_id']
)


def track_request(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            response = f(*args, **kwargs)
            status_code = response.status_code if hasattr(response, 'status_code') else 200
            
            # Track metrics
            REQUEST_COUNT.labels(
                method=f.__name__,
                endpoint=f.__name__,
                http_status=status_code
            ).inc()
            
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=f.__name__,
                endpoint=f.__name__
            ).observe(duration)
            
            return response
            
        except Exception as e:
            REQUEST_COUNT.labels(
                method=f.__name__,
                endpoint=f.__name__,
                http_status=500
            ).inc()
            raise
    
    return wrapper


def metrics_endpoint():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
