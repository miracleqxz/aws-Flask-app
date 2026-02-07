from flask import Flask, jsonify, request, render_template, Response
from config import Config
import boto3
import os
import logging
import json

from database.rate_limiter import check_rate_limit, get_rate_limit_status
from database.movies_db import (
    get_movies_paginated, get_all_genres, get_movies_by_genre,
    get_movies_by_genres, get_similar_movies, get_movie_by_id,
    get_all_movies, log_search_query
)
from database.redis_cache import get_cached_search, set_cached_search, get_cache_stats, clear_search_cache
from database.movie_cache import get_cached_movie, set_cached_movie, clear_movie_cache
from database.meilisearch_sync import search_movies_meili
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


# ── Helpers ──

def invoke_lambda(function_name, payload, async_invoke=False):
    """Invoke a Lambda function and return parsed response body."""
    client = boto3.client('lambda', region_name=Config.AWS_REGION)
    response = client.invoke(
        FunctionName=function_name,
        InvocationType='Event' if async_invoke else 'RequestResponse',
        Payload=json.dumps(payload)
    )
    if async_invoke:
        return {'status': 'ok'}

    result = json.loads(response['Payload'].read().decode())

    if 'FunctionError' in response:
        raise RuntimeError(f"Lambda error: {result}")

    if 'body' in result:
        result = json.loads(result['body'])
    return result


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


#  Pages

@app.route('/')
@track_request
def home():
    return render_template('index.html')


@app.route('/movies')
@track_request
def movies_page():
    ai_mode = request.args.get('ai')

    if ai_mode:
        return render_template(
            'ai_movies.html',
            ai_chat_api_url=os.getenv('AI_CHAT_API_URL', ''),
            ai_chat_api_key=os.getenv('AI_CHAT_API_KEY', '')
        )

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

    cached_movie, from_cache = get_cached_movie(movie_id)
    if cached_movie and from_cache:
        return render_template('movie_detail.html', movie=cached_movie, from_cache=True)

    movie = get_movie_by_id(movie_id)
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    movie_dict = dict(movie)
    set_cached_movie(movie_id, movie_dict, ttl=600)
    return render_template('movie_detail.html', movie=movie_dict, from_cache=False)


#  Core API

@app.route('/health')
@track_request
def health():
    return jsonify({'status': 'healthy', 'service': 'flask-app', 'version': '1.0.0'})


@app.route('/info')
def info():
    import sys
    return jsonify({
        'app_name': 'Service Checker AWS',
        'author': 'Pavlo',
        'python_version': sys.version.split()[0],
        'deployment': 'AWS ECS'
    })


@app.route('/metrics')
@track_request
def metrics():
    return metrics_endpoint()


#  Search & Movies API

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
            result, from_cache = cached_result, True
        else:
            CACHE_MISS_COUNT.inc()
            result = search_movies_meili(query)
            set_cached_search(query, result, ttl=300)
            from_cache = False

        SEARCH_RESULTS_COUNT.observe(len(result))
        log_search_query(query, len(result))
        send_search_event(query, len(result), from_cache)

        return jsonify({'results': result, 'count': len(result), 'cached': from_cache})
    except Exception as e:
        logging.error(f"Search error: {e}")
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500


@app.route('/api/poster/<filename>')
def get_poster(filename):
    from database.s3_storage import download_poster
    try:
        image_data = download_poster(filename)
        if image_data:
            return Response(image_data, mimetype='image/jpeg')
        return jsonify({'error': 'Poster not found'}), 404
    except Exception as e:
        logging.error(f"Poster error for {filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/movies/featured')
def api_featured_movies():
    limit = request.args.get('limit', 8, type=int)
    movies = get_all_movies()[:limit]

    return jsonify({
        'movies': [{
            'id': m['id'],
            'title': m['title'],
            'rating': float(m['rating']),
            'year': m['year'],
            'genres': m.get('genres', []),
            'genre': m.get('genre', ''),
            'poster_filename': m['poster_filename']
        } for m in movies]
    })


@app.route('/api/movies/genres')
def api_movies_genres():
    try:
        movies = get_all_movies()
        genre_counts = {}
        for movie in movies:
            genre = movie.get('genre', 'Unknown')
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        return jsonify({
            'total_genres': len(genre_counts),
            'genres': [{'name': g, 'count': c} for g, c in sorted_genres]
        })
    except Exception as e:
        logging.error(f"Genres error: {e}")
        return jsonify({'error': str(e)}), 500


#  Cache & Analytics API

@app.route('/api/cache/stats')
def api_cache_stats():
    stats = get_cache_stats()
    if stats is None:
        return jsonify({'connected': False, 'error': 'Redis unavailable', 'hits': 0, 'misses': 0, 'hit_rate': '0%', 'cached_keys': 0})

    total = stats['hits'] + stats['misses']
    hit_rate = (stats['hits'] / total * 100) if total > 0 else 0
    return jsonify({
        'connected': True,
        'hits': stats['hits'],
        'misses': stats['misses'],
        'hit_rate': f"{hit_rate:.1f}%",
        'cached_keys': stats['keys_count']
    })


@app.route('/api/cache/clear', methods=['POST'])
def api_cache_clear():
    count = clear_search_cache()
    return jsonify({'message': f'Cleared {count} cached searches'})


@app.route('/api/cache/clear/movies', methods=['POST'])
def clear_movies_cache_endpoint():
    count = clear_movie_cache()
    return jsonify({'message': f'Cleared {count} cached movies'})


@app.route('/api/analytics/popular')
def api_popular_searches():
    limit = request.args.get('limit', 10, type=int)
    return jsonify({'popular_searches': get_popular_searches(limit)})


@app.route('/api/analytics/stats')
def api_analytics_stats():
    return jsonify(get_search_stats())


@app.route('/api/sqs/stats')
def api_sqs_stats():
    try:
        sqs = boto3.client('sqs', region_name=Config.AWS_REGION)
        response = sqs.get_queue_attributes(
            QueueUrl=Config.SQS_QUEUE_URL,
            AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible', 'ApproximateNumberOfMessagesDelayed']
        )
        attrs = response['Attributes']
        return jsonify({
            'queue_url': Config.SQS_QUEUE_URL,
            'messages': {
                'approximate_count': int(attrs.get('ApproximateNumberOfMessages', 0)),
                'in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
                'delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


#  Backend Control (Lambda orchestration)

@app.route('/api/backend/status')
def backend_status():
    try:
        backend = invoke_lambda(Config.LAMBDA_BACKEND_CONTROL, {'action': 'status'})
        ai_agent = invoke_lambda(Config.LAMBDA_AI_AGENT_CONTROL, {'action': 'status'})

        backend_state = backend.get('state', 'unknown')
        ai_state = ai_agent.get('state', 'unknown')
        overall = 'running' if backend_state == 'running' and ai_state == 'running' else 'stopped'

        return jsonify({
            'state': overall,
            'instance_id': backend.get('instance_id'),
            'private_ip': backend.get('private_ip'),
            'heartbeat': backend.get('heartbeat'),
            'backend': backend,
            'ai_agent': ai_agent
        })
    except Exception as e:
        logging.error(f"Backend status error: {e}")
        return jsonify({'status': 'error', 'state': 'unknown', 'message': str(e)}), 500


@app.route('/api/backend/start', methods=['POST'])
def backend_start():
    try:
        backend = invoke_lambda(Config.LAMBDA_BACKEND_CONTROL, {'action': 'start'})
        ai_agent = invoke_lambda(Config.LAMBDA_AI_AGENT_CONTROL, {'action': 'start'})

        if ai_agent.get('state') not in ('running', 'pending', 'starting'):
            error_msg = ai_agent.get('message', ai_agent.get('error', str(ai_agent)))
            logging.warning(f"AI agent not running after start: {ai_agent}")
            return jsonify({
                'status': 'error',
                'message': error_msg or 'AI agent did not start',
                'backend': backend,
                'ai_agent': ai_agent
            }), 500

        return jsonify({'backend': backend, 'ai_agent': ai_agent, 'status': 'started'})
    except Exception as e:
        logging.error(f"Backend start error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/backend/stop', methods=['POST'])
def backend_stop():
    try:
        backend = invoke_lambda(Config.LAMBDA_BACKEND_CONTROL, {'action': 'stop'})
        ai_agent = invoke_lambda(Config.LAMBDA_AI_AGENT_CONTROL, {'action': 'stop'})
        return jsonify({'backend': backend, 'ai_agent': ai_agent, 'status': 'stopped'})
    except Exception as e:
        logging.error(f"Backend stop error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/backend/heartbeat', methods=['POST'])
def backend_heartbeat():
    try:
        invoke_lambda(Config.LAMBDA_BACKEND_CONTROL, {'action': 'heartbeat'}, async_invoke=True)
        return jsonify({'status': 'ok'})
    except Exception as e:
        logging.error(f"Heartbeat error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


#  Data Pipeline

@app.route('/api/data/sync', methods=['POST'])
def data_sync():
    rate_check = check_rate_limit('data_sync', cooldown_seconds=300)
    if not rate_check['allowed']:
        return jsonify({
            'status': 'rate_limited',
            'message': rate_check['message'],
            'retry_after': rate_check['retry_after']
        }), 429

    try:
        result = invoke_lambda(Config.LAMBDA_DATA_PIPELINE, {'action': 'sync'})
        return jsonify(result)
    except Exception as e:
        logging.error(f"Data sync error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data/status')
def data_status():
    try:
        result = invoke_lambda(Config.LAMBDA_DATA_PIPELINE, {'action': 'status'})
        return jsonify(result)
    except Exception as e:
        logging.error(f"Data status error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data/rate-limit-status')
def data_rate_limit_status():
    return jsonify(get_rate_limit_status('data_sync', cooldown_seconds=300))


#  AI Agent API (consumed by AI Flask app)

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

    genres = MOOD_TO_GENRES.get(mood.lower(), ["Drama"])
    results = get_movies_by_genres(genres, limit)
    return jsonify({'movies': results, 'count': len(results), 'mood': mood})



#  Entry point

if __name__ == '__main__':
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )