from flask import Flask, jsonify
from config import Config
from services.redis_check import check_redis
from services.postgres_check import check_postgres
from services.rabbitmq_check import check_rabbitmq
from services.elasticsearch_check import check_elasticsearch
from services.minio_check import check_minio
from services.consul_check import check_consul
from services.prometheus_check import check_prometheus
from database.meilisearch_sync import search_movies_meili
from database.s3_storage import download_poster_s3, poster_exists_s3
from flask import request
from database.minio_storage import download_poster, poster_exists
from flask import send_file
import io
from flask import render_template
from database.movies_db import get_all_movies, get_movie_by_id
from database.movie_cache import get_cached_movie, set_cached_movie
from database.redis_cache import get_cached_search, set_cached_search
from metrics import (
    metrics_endpoint, track_request,
    CACHE_HIT_COUNT, CACHE_MISS_COUNT,
    SEARCH_QUERY_COUNT, SEARCH_RESULTS_COUNT,
    MOVIE_VIEWS
)
import json


app = Flask(__name__)
app.config.from_object(Config)


@app.route('/')
@track_request
def home():
    """Main page"""
    return render_template('index.html')


@app.route('/info')
def info():
    """Application information"""
    import sys

    return jsonify({
        'app_name': 'Service Checker',
        'author': 'Pavlo',
        'python_version': sys.version.split()[0]
    })


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


@app.route('/check/rabbitmq')
def check_rabbitmq_endpoint():
    result = check_rabbitmq()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/elasticsearch')
def check_elasticsearch_endpoint():
    result = check_elasticsearch()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/minio')
def check_minio_endpoint():
    result = check_minio()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code

@app.route('/check/consul')
def check_consul_endpoint():
    result = check_consul()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code

@app.route('/check/prometheus')
def check_prometheus_endpoint():
    result = check_prometheus()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code

@app.route('/api/search')
def search():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    SEARCH_QUERY_COUNT.inc()
    
    try:
        cached_result = get_cached_search(query)
        
        if cached_result:
            CACHE_HIT_COUNT.inc()
            result = cached_result
            from_cache = True
        else:
            CACHE_MISS_COUNT.inc()
            result = search_movies_meili(query)
            set_cached_search(query, result, ttl=300)
            from_cache = False
        
        SEARCH_RESULTS_COUNT.observe(len(result))
        log_search_query(query, len(result))
        
        from database.sqs_analytics import send_search_event
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
    from database.redis_cache import get_cache_stats
    
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
    from database.redis_cache import clear_search_cache
    
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
    from database.rabbitmq_analytics import get_queue_stats
    
    stats = get_queue_stats()
    
    if stats is None:
        return jsonify({'error': 'Failed to get stats'}), 500
    
    return jsonify(stats)


@app.route('/service/<service_name>')
def service_detail(service_name):
    check_functions = {
        'postgres': check_postgres,
        'redis': check_redis,
        'rabbitmq': check_rabbitmq,
        'elasticsearch': check_elasticsearch,
        'minio': check_minio,
        'consul': check_consul,
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
    
    
    cached_movie, from_cache = get_cached_movie(movie_id)
    
    
    print(f"Movie ID: {movie_id}")
    print(f"Cached movie: {cached_movie is not None}")
    print(f"From cache: {from_cache}")
    
    if cached_movie and from_cache: 
        print(f"Serving from CACHE")
        return render_template(
            'movie_detail.html',
            movie=cached_movie,
            from_cache=True
        )
    
    
    print(f"Fetching from DATABASE")
    movie = get_movie_by_id(movie_id)
    
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    
    movie_dict = dict(movie)
    
    # Store in cache
    success = set_cached_movie(movie_id, movie_dict, ttl=600)
    print(f"Cached: {success}")
    
    return render_template(
        'movie_detail.html',
        movie=movie_dict,
        from_cache=False
    )

@app.route('/api/cache/clear/movies', methods=['POST'])
def clear_movies_cache():
    from database.movie_cache import clear_movie_cache
    
    count = clear_movie_cache()
    return jsonify({
        'message': f'Cleared {count} cached movies'
    })


@app.route('/health')
@track_request
def health():
    """Health check endpoint for Kubernetes"""
    return jsonify({
        'status': 'healthy',
        'service': 'flask-app',
        'version': '1.0.0'
    }), 200



@app.route('/metrics')
@track_request
def metrics():
    """Prometheus metrics endpoint"""
    return metrics_endpoint()



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )



