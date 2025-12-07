from flask import Flask, jsonify, request, render_template, send_file, Response
from config import Config
import logging
import io
import json

from services.redis_check import check_redis
from services.postgres_check import check_postgres
from services.meilisearch_check import check_meilisearch  
from services.s3_check import check_s3  
from services.sqs_check import check_sqs  
from services.consul_check import check_consul
from services.prometheus_check import check_prometheus
from services.nginx_check import check_nginx
from services.grafana_check import check_grafana

from database.movies_db import get_all_movies, get_movie_by_id, log_search_query
from database.redis_cache import get_cached_search, set_cached_search, get_cache_stats, clear_search_cache
from database.movie_cache import get_cached_movie, set_cached_movie, clear_movie_cache
from database.meilisearch_sync import search_movies_meili  
from database.s3_storage import download_poster, poster_exists  
from database.sqs_analytics import send_search_event  
from database.analytics_db import get_popular_searches, get_search_stats

from metrics import (
    metrics_endpoint, track_request,
    CACHE_HIT_COUNT, CACHE_MISS_COUNT,
    SEARCH_QUERY_COUNT, SEARCH_RESULTS_COUNT,
    MOVIE_VIEWS
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        'app_name': 'Service Checker AWS',
        'author': 'Pavlo',
        'python_version': sys.version.split()[0],
        'deployment': 'AWS ECS'
    })

@app.route('/health')
@track_request
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'flask-app',
        'version': '1.0.0'
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


@app.route('/check/s3')  
def check_s3_endpoint():
    result = check_s3()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/sqs')  
def check_sqs_endpoint():
    result = check_sqs()
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


@app.route('/check/nginx')
def check_nginx_endpoint():
    result = check_nginx()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


@app.route('/check/grafana')
def check_grafana_endpoint():
    result = check_grafana()
    status_code = 200 if result['status'] == 'healthy' else 503
    return jsonify(result), status_code


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
            set_cached_search(query, result, ttl=300)
            from_cache = False
        
        SEARCH_RESULTS_COUNT.observe(len(result))
        
        # Log to PostgreSQL
        log_search_query(query, len(result))
        
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
def get_poster(filename):
    from database.s3_storage import download_poster
    
    print(f"=== Poster request: {filename} ===")
    
    try:
        image_data = download_poster(filename)
        
        if image_data:
            print(f"Returning {len(image_data)} bytes")
            return Response(image_data, mimetype='image/jpeg')
        else:
            print("No image data returned")
            return jsonify({'error': 'Poster not found'}), 404
            
    except Exception as e:
        print(f"ENDPOINT ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/movies')
@track_request
def movies_list():
    movies = get_all_movies()
    return render_template('movies.html', movies=movies)


@app.route('/movie/<int:movie_id>')
@track_request
def movie_detail(movie_id):
    
    MOVIE_VIEWS.labels(movie_id=movie_id).inc()
    
    # Check cache first
    cached_movie, from_cache = get_cached_movie(movie_id)
    
    if cached_movie and from_cache:
        return render_template(
            'movie_detail.html',
            movie=cached_movie,
            from_cache=True
        )
    
    # Fetch from database
    movie = get_movie_by_id(movie_id)
    
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    movie_dict = dict(movie)
    
    # Store in cache
    set_cached_movie(movie_id, movie_dict, ttl=600)
    
    return render_template(
        'movie_detail.html',
        movie=movie_dict,
        from_cache=False
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


@app.route('/api/cache/clear/movies', methods=['POST'])
def clear_movies_cache_endpoint():
    count = clear_movie_cache()
    
    return jsonify({
        'message': f'Cleared {count} cached movies'
    })


@app.route('/api/analytics/popular')
def api_popular_searches():
    limit = request.args.get('limit', 10, type=int)
    popular = get_popular_searches(limit)
    
    return jsonify({
        'popular_searches': popular
    })


@app.route('/api/analytics/stats')
def api_analytics_stats():
    stats = get_search_stats()
    
    return jsonify(stats)


@app.route('/api/sqs/stats')  
def api_sqs_stats():
    try:
        result = check_sqs()
        
        if result['status'] == 'unhealthy':
            return jsonify({'error': 'SQS not available'}), 503
        
        messages = result['details']['messages']
        
        return jsonify({
            'queue_url': Config.SQS_QUEUE_URL,
            'messages': {
                'approximate_count': messages['approximate_count'],
                'in_flight': messages['in_flight'],
                'delayed': messages['delayed']
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/service/<service_name>')
def service_detail(service_name):
    check_functions = {
        'postgres': check_postgres,
        'redis': check_redis,
        'meilisearch': check_meilisearch,  
        's3': check_s3,  
        'sqs': check_sqs,  
        'consul': check_consul,
        'prometheus': check_prometheus,
        'nginx': check_nginx,
        'grafana': check_grafana
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