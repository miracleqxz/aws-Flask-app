from flask import Flask, jsonify, request, render_template, send_file
from config import Config
import io
import json


from database.movies_db import get_all_movies, get_movie_by_id, log_search_query
from database.redis_cache import get_cached_search, set_cached_search, get_cache_stats, clear_search_cache
from database.meilisearch_sync import search_movies_meili
from database.s3_storage import download_poster as download_poster_s3, poster_exists as poster_exists_s3
from database.sqs_analytics import send_search_event
from database.analytics_db import get_popular_searches, get_search_stats


from services import (
    check_consul,
    check_redis,
    check_postgres,
    check_meilisearch,
    check_sqs,
    check_s3,
    check_prometheus
)


from metrics import (
    metrics_endpoint, track_request,
    CACHE_HIT_COUNT, CACHE_MISS_COUNT,
    SEARCH_QUERY_COUNT, SEARCH_RESULTS_COUNT,
    MOVIE_VIEWS
)

app = Flask(__name__)
app.config.from_object(Config)



@app.route('/')
@track_request
def home():
    return render_template('index.html')


@app.route('/info')
def info():
    import sys
    return jsonify({
        'app_name': 'Movie Service Checker',
        'author': 'Pavel',
        'python_version': sys.version.split()[0],
        'environment': 'AWS ECS',
        'services': {
            'database': 'RDS PostgreSQL',
            'cache': 'Redis',
            'search': 'Meilisearch',
            'queue': 'Amazon SQS',
            'storage': 'S3',
            'discovery': 'Consul',
            'monitoring': 'Prometheus + Grafana'
        }
    })


@app.route('/health')
@track_request
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'flask-app',
        'version': '2.0.0-aws'
    }), 200


@app.route('/check/redis')
def check_redis_endpoint():
    result = check_redis()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/postgres')
def check_postgres_endpoint():
    result = check_postgres()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/meilisearch')
def check_meilisearch_endpoint():
    result = check_meilisearch()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/consul')
def check_consul_endpoint():
    result = check_consul()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/sqs')
def check_sqs_endpoint():
    result = check_sqs()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/s3')
def check_s3_endpoint():
    result = check_s3()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/prometheus')
def check_prometheus_endpoint():
    result = check_prometheus()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/all')
def check_all_services():
    services = {
        'postgres': check_postgres(),
        'redis': check_redis(),
        'meilisearch': check_meilisearch(),
        'consul': check_consul(),
        'sqs': check_sqs(),
        's3': check_s3(),
        'prometheus': check_prometheus()
    }
    
    all_healthy = all(s['status'] == 'healthy' for s in services.values())
    overall_status = 'healthy' if all_healthy else 'degraded'
    
    return jsonify({
        'overall_status': overall_status,
        'services': services
    }), 200 if all_healthy else 503


@app.route('/api/search')
def search():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    SEARCH_QUERY_COUNT.inc()
    
    try:
        # Check cache first
        cached_result = get_cached_search(query)
        
        if cached_result:
            CACHE_HIT_COUNT.inc()
            result = cached_result
            from_cache = True
        else:
            CACHE_MISS_COUNT.inc()
            # Search in Meilisearch
            result = search_movies_meili(query)
            # Cache results
            set_cached_search(query, result, ttl=300)
            from_cache = False
        
        SEARCH_RESULTS_COUNT.observe(len(result))
        
        # Log to database
        log_search_query(query, len(result))
        
        # Send analytics event to SQS
        send_search_event(query, len(result), from_cache)
        
        return jsonify({
            'results': result,
            'count': len(result),
            'cached': from_cache
        })
        
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500


@app.route('/api/poster/<filename>')
def api_poster(filename):
    if not poster_exists_s3(filename):
        return jsonify({'error': 'Poster not found'}), 404
    
    poster_data = download_poster_s3(filename)
    
    if poster_data is None:
        return jsonify({'error': 'Failed to retrieve poster'}), 500
    
    return send_file(
        io.BytesIO(poster_data),
        mimetype='image/jpeg',
        download_name=filename
    )


@app.route('/api/cache/stats')
def api_cache_stats():
    stats = get_cache_stats()
    
    if stats is None:
        return jsonify({'error': 'Failed to get stats'}), 500
    
    # Calculate hit rate
    total = stats['hits'] + stats['misses']
    hit_rate = (stats['hits'] / total * 100) if total > 0 else 0
    
    return jsonify({
        'hits': stats['hits'],
        'misses': stats['misses'],
        'hit_rate': f"{hit_rate:.1f}%",
        'cached_keys': stats['keys_count']
    })


@app.route('/api/cache/clear', methods=['POST'])
def api_cache_clear():
    count = clear_search_cache()
    return jsonify({
        'message': f'Cleared {count} cached searches'
    })


@app.route('/api/analytics/popular')
def api_popular_searches():
    from database.analytics_db import get_popular_searches
    
    limit = request.args.get('limit', 10, type=int)
    popular = get_popular_searches(limit)
    
    return jsonify({
        'popular_searches': popular
    })


@app.route('/api/analytics/stats')
def api_analytics_stats():
    from database.analytics_db import get_search_stats
    
    stats = get_search_stats()
    return jsonify(stats)


@app.route('/api/queue/stats')
def api_queue_stats():
    try:
        import boto3
        sqs = boto3.client('sqs', region_name=Config.AWS_REGION)
        response = sqs.get_queue_attributes(
            QueueUrl=Config.SQS_QUEUE_URL,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed'
            ]
        )
        
        attrs = response['Attributes']
        return jsonify({
            'messages_available': int(attrs.get('ApproximateNumberOfMessages', 0)),
            'messages_in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'messages_delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0)),
            'queue_url': Config.SQS_QUEUE_URL
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/service/<service_name>')
def service_detail(service_name):
    check_functions = {
        'postgres': check_postgres,
        'redis': check_redis,
        'meilisearch': check_meilisearch,
        'consul': check_consul,
        'sqs': check_sqs,
        's3': check_s3,
        'prometheus': check_prometheus
    }
    
    if service_name not in check_functions:
        return jsonify({'error': 'Service not found'}), 404
    
    result = check_functions[service_name]()
    
    return render_template(
        'service_detail.html',
        service_name=service_name.upper(),
        status=result['status'],
        data=result
    )


@app.route('/movies')
@track_request
def movies_list():
    movies = get_all_movies()
    return render_template('movies.html', movies=movies)


@app.route('/movie/<int:movie_id>')
@track_request
def movie_detail(movie_id):
    MOVIE_VIEWS.labels(movie_id=movie_id).inc()
    
    # Try to get from cache
    try:
        from database.redis_cache import get_redis_client
        client = get_redis_client()
        cache_key = f"movie:{movie_id}"
        cached = client.get(cache_key)
        
        if cached:
            movie_dict = json.loads(cached)
            return render_template(
                'movie_detail.html',
                movie=movie_dict,
                from_cache=True
            )
    except:
        pass
    
    # Get from database
    movie = get_movie_by_id(movie_id)
    
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    movie_dict = dict(movie)
    
    # Store in cache
    try:
        from database.redis_cache import get_redis_client
        client = get_redis_client()
        cache_key = f"movie:{movie_id}"
        client.setex(cache_key, 600, json.dumps(movie_dict))
    except:
        pass
    
    return render_template(
        'movie_detail.html',
        movie=movie_dict,
        from_cache=False
    )


@app.route('/metrics')
@track_request
def metrics():
    return metrics_endpoint()


if __name__ == '__main__':
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )