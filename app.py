from flask import Flask, jsonify, request, render_template, send_file, Response
from config import Config
import boto3
import os
import logging
import io
import json

from services.redis_check import check_redis
from services.postgres_check import check_postgres
from services.meilisearch_check import check_meilisearch  
from services.consul_check import check_consul
from services.prometheus_check import check_prometheus
from services.nginx_check import check_nginx
from services.grafana_check import check_grafana
from services.sqs_check import check_sqs  
from services.s3_check import check_s3

from database.movies_db import get_movies_paginated, get_all_genres, get_movies_by_genre, get_similar_movies, get_movie_by_id, get_all_movies, log_search_query
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

@app.route('/check/sqs')
def check_sqs_endpoint(): 
    result = check_sqs()
    return jsonify(result)

@app.route('/check/s3')
def check_s3_endpoint():
    result = check_s3()
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
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    if page < 1:
        page = 1
    
    result = get_movies_paginated(page, per_page)
    
    return render_template(
        'movies.html',
        movies=result['movies'],
        page=result['page'],
        pages=result['pages'],
        total=result['total'],
        per_page=per_page
    )


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


@app.route('/api/movies/featured')
def api_featured_movies():
    movies = get_all_movies()
    featured = movies[:8]
    
    # Convert to dict format
    result = []
    for movie in featured:
        result.append({
            'id': movie['id'],
            'title': movie['title'],
            'rating': float(movie['rating']),
            'year': movie['year'],
            'genre': movie['genre'],
            'poster_filename': movie['poster_filename']
        })
    
    return jsonify({'movies': result})

@app.route('/api/movies/genres')
def api_movies_genres():
    try:
        movies = get_all_movies()
        
        genre_counts = {}
        for movie in movies:
            genre = movie.get('genre', 'Unknown')
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
        
        sorted_genres = sorted(
            genre_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return jsonify({
            'total_genres': len(genre_counts),
            'genres': [
                {'name': genre, 'count': count}
                for genre, count in sorted_genres
            ]
        })
    except Exception as e:
        logging.error(f"Genres error: {e}")
        return jsonify({'error': str(e)}), 500


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

@app.route('/api/backend/status')
def backend_status():
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        response = lambda_client.invoke(
            FunctionName=Config.LAMBDA_BACKEND_CONTROL,
            InvocationType='RequestResponse',
            Payload=json.dumps({'action': 'status'})
        )
        
        result = json.loads(response['Payload'].read().decode())
        
        # Handle API Gateway response format
        if 'body' in result:
            return jsonify(json.loads(result['body']))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Backend status error: {e}")
        return jsonify({
            'status': 'error',
            'state': 'unknown',
            'message': str(e)
        }), 500


@app.route('/api/backend/start', methods=['POST'])
def backend_start():
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        response = lambda_client.invoke(
            FunctionName=Config.LAMBDA_BACKEND_CONTROL,
            InvocationType='RequestResponse',
            Payload=json.dumps({'action': 'start'})
        )
        
        result = json.loads(response['Payload'].read().decode())
        
        if 'body' in result:
            return jsonify(json.loads(result['body']))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Backend start error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/backend/stop', methods=['POST'])
def backend_stop():
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        response = lambda_client.invoke(
            FunctionName=Config.LAMBDA_BACKEND_CONTROL,
            InvocationType='RequestResponse',
            Payload=json.dumps({'action': 'stop'})
        )
        
        result = json.loads(response['Payload'].read().decode())
        
        if 'body' in result:
            return jsonify(json.loads(result['body']))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Backend stop error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/backend/heartbeat', methods=['POST'])
def backend_heartbeat():
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        response = lambda_client.invoke(
            FunctionName=Config.LAMBDA_BACKEND_CONTROL,
            InvocationType='Event',  # Async - don't wait for response
            Payload=json.dumps({'action': 'heartbeat'})
        )
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logging.error(f"Heartbeat error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
@app.route('/api/data/sync', methods=['POST'])
def data_sync():
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        response = lambda_client.invoke(
            FunctionName=Config.LAMBDA_DATA_PIPELINE,
            InvocationType='RequestResponse',
            Payload=json.dumps({'action': 'sync'})
        )
        
        result = json.loads(response['Payload'].read().decode())
        
        if 'body' in result:
            return jsonify(json.loads(result['body']))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Data sync error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data/status')
def data_status():
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        response = lambda_client.invoke(
            FunctionName=Config.LAMBDA_DATA_PIPELINE,
            InvocationType='RequestResponse',
            Payload=json.dumps({'action': 'status'})
        )
        
        result = json.loads(response['Payload'].read().decode())
        
        if 'body' in result:
            return jsonify(json.loads(result['body']))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Data status error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/api/ai/search')
def ai_search():
    query = request.args.get('q', '')
    limit = request.args.get('limit', 5, type=int)
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    results = search_movies_meili(query, limit)
    return jsonify({'movies': results, 'count': len(results)})


@app.route('/api/ai/genres')
def ai_genres():
    genres = get_all_genres()
    return jsonify({'genres': genres, 'count': len(genres)})


@app.route('/api/ai/by-genre')
def ai_by_genre():
    genre = request.args.get('genre', '')
    limit = request.args.get('limit', 5, type=int)
    
    if not genre:
        return jsonify({'error': 'Query parameter "genre" is required'}), 400
    
    results = get_movies_by_genre(genre, limit)
    return jsonify({'movies': results, 'count': len(results)})


@app.route('/api/ai/similar/<int:movie_id>')
def ai_similar(movie_id):
    limit = request.args.get('limit', 5, type=int)
    
    results = get_similar_movies(movie_id, limit)
    return jsonify({'movies': results, 'count': len(results)})


@app.route('/api/ai/movie/<int:movie_id>')
def ai_movie_detail(movie_id):
    movie = get_movie_by_id(movie_id)
    
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    return jsonify({'movie': dict(movie)})

@app.route('/api/ai/by-mood')
def ai_by_mood():
    mood = request.args.get('mood', '')
    limit = request.args.get('limit', 5, type=int)
    
    if not mood:
        return jsonify({'error': 'Query parameter "mood" is required'}), 400
    
    MOOD_TO_GENRES = {
        "uplifting": ["Comedy", "Romance", "Adventure"],
        "dark": ["Thriller", "Crime", "Drama"],
        "intense": ["Action", "Thriller", "War"],
        "romantic": ["Romance", "Drama"],
        "funny": ["Comedy"],
        "thought-provoking": ["Sci-Fi", "Drama", "Mystery"],
        "scary": ["Horror", "Thriller"],
        "epic": ["Action", "Adventure", "Fantasy"],
        "emotional": ["Drama", "Romance"],
        "nostalgic": ["Adventure", "Fantasy", "Family"],
    }
    
    genres = MOOD_TO_GENRES.get(mood.lower(), ["Drama"])
    results = get_movies_by_genres(genres, limit)
    
    return jsonify({'movies': results, 'count': len(results), 'mood': mood})

if __name__ == '__main__':
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )