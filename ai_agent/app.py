#!/usr/bin/env python3
import os
import json
import logging
import requests
import redis
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

CURSOR_API_KEY = os.getenv('CURSOR_API_KEY')
if not CURSOR_API_KEY:
    raise ValueError("CURSOR_API_KEY environment variable is required")

CURSOR_API_BASE_URL = os.getenv('CURSOR_API_BASE_URL')
if not CURSOR_API_BASE_URL:
    raise ValueError("CURSOR_API_BASE_URL environment variable is required")

CURSOR_MODEL = os.getenv('CURSOR_MODEL')
if not CURSOR_MODEL:
    raise ValueError("CURSOR_MODEL environment variable is required")

MOVIE_API_BASE_URL = os.getenv('MOVIE_API_BASE_URL')
if not MOVIE_API_BASE_URL:
    raise ValueError("MOVIE_API_BASE_URL environment variable is required")

LAMBDA_API_URL = os.getenv('LAMBDA_API_URL', '')
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv('HEARTBEAT_INTERVAL_SECONDS', '30'))

REDIS_HOST = os.getenv('REDIS_HOST')
if not REDIS_HOST:
    raise ValueError("REDIS_HOST environment variable is required")

REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

POSTGRES_HOST = os.getenv('POSTGRES_HOST')
if not POSTGRES_HOST:
    raise ValueError("POSTGRES_HOST environment variable is required")

POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB')
if not POSTGRES_DB:
    raise ValueError("POSTGRES_DB environment variable is required")

POSTGRES_USER = os.getenv('POSTGRES_USER')
if not POSTGRES_USER:
    raise ValueError("POSTGRES_USER environment variable is required")

POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
if not POSTGRES_PASSWORD:
    raise ValueError("POSTGRES_PASSWORD environment variable is required")

MEILISEARCH_HOST = os.getenv('MEILISEARCH_HOST')
if not MEILISEARCH_HOST:
    raise ValueError("MEILISEARCH_HOST environment variable is required")

MEILISEARCH_PORT = os.getenv('MEILISEARCH_PORT', '7700')

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')

AI_CHAT_MAX_REQUESTS = int(os.getenv('AI_CHAT_MAX_REQUESTS', '10'))
AI_CHAT_WINDOW_SECONDS = int(os.getenv('AI_CHAT_WINDOW_SECONDS', '60'))
AI_CHAT_IDLE_TIMEOUT_MINUTES = int(os.getenv('AI_CHAT_IDLE_TIMEOUT_MINUTES', '5'))

client = OpenAI(
    api_key=CURSOR_API_KEY,
    base_url=CURSOR_API_BASE_URL
)

last_heartbeat = datetime.now(timezone.utc)


def get_redis_client():
    try:
        return redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True,
            socket_timeout=5
        )
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


def send_heartbeat():
    global last_heartbeat
    if not LAMBDA_API_URL:
        return

    try:
        response = requests.post(
            f"{LAMBDA_API_URL}/heartbeat",
            timeout=5
        )
        if response.status_code == 200:
            last_heartbeat = datetime.now(timezone.utc)
            logger.info("Heartbeat sent successfully")
        else:
            logger.warning(f"Heartbeat failed with status {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending heartbeat: {e}")


def search_movies(query, limit=10):
    try:
        response = requests.get(
            f"{MOVIE_API_BASE_URL}/api/search",
            params={'q': query, 'limit': limit},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('results', [])
        logger.error(f"Search API returned {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error searching movies: {e}")
        return []


def get_movie_details(movie_id):
    try:
        response = requests.get(
            f"{MOVIE_API_BASE_URL}/api/ai/movie/{movie_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('movie')
        logger.error(f"Movie details API returned {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error getting movie details: {e}")
        return None


def search_youtube_trailer(movie_title, year=None):
    if not YOUTUBE_API_KEY:
        logger.warning("YouTube API key not configured")
        return None

    try:
        query = f"{movie_title} trailer"
        if year:
            query += f" {year}"

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'id',
            'q': query,
            'type': 'video',
            'maxResults': 1,
            'key': YOUTUBE_API_KEY,
            'videoCategoryId': '1'
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            if items:
                video_id = items[0]['id']['videoId']
                logger.info(f"Found YouTube trailer for {movie_title}: {video_id}")
                return video_id

        logger.warning(f"No YouTube trailer found for {movie_title}")
        return None
    except Exception as e:
        logger.error(f"Error searching YouTube trailer: {e}")
        return None


def check_rate_limit(user_id):
    r = get_redis_client()
    if not r:
        return {'allowed': True, 'remaining': AI_CHAT_MAX_REQUESTS}

    key = f"ai_chat_rate_limit:{user_id}"
    current_time = time.time()

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, current_time - AI_CHAT_WINDOW_SECONDS)
        pipe.zcard(key)
        pipe.zadd(key, {str(current_time): current_time})
        pipe.expire(key, AI_CHAT_WINDOW_SECONDS)
        results = pipe.execute()

        current_count = results[1]

        if current_count >= AI_CHAT_MAX_REQUESTS:
            oldest_request = r.zrange(key, 0, 0, withscores=True)
            if oldest_request:
                reset_time = int(oldest_request[0][1] + AI_CHAT_WINDOW_SECONDS)
                remaining_seconds = reset_time - int(current_time)
                return {
                    'allowed': False,
                    'remaining': 0,
                    'reset_at': reset_time,
                    'message': f'Rate limit exceeded. Try again in {remaining_seconds} seconds.'
                }

        remaining = AI_CHAT_MAX_REQUESTS - current_count - 1
        return {
            'allowed': True,
            'remaining': max(0, remaining),
            'reset_at': int(current_time) + AI_CHAT_WINDOW_SECONDS
        }
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return {'allowed': True, 'remaining': AI_CHAT_MAX_REQUESTS}


def update_activity(user_id):
    r = get_redis_client()
    if not r:
        return

    key = f"ai_chat_activity:{user_id}"
    try:
        r.setex(key, AI_CHAT_IDLE_TIMEOUT_MINUTES * 60, str(time.time()))
    except Exception as e:
        logger.error(f"Failed to update activity: {e}")


def get_available_functions():
    return [
        {
            "type": "function",
            "function": {
                "name": "search_movies",
                "description": "Search for movies in the database by keywords, genre, mood, or description. Use this when the user wants to find movies.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query - can be keywords, genre name, mood (like 'sad', 'funny', 'romantic'), or movie description"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_movie_details",
                "description": "Get detailed information about a specific movie by its ID. Use this after finding a movie to show full details to the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "movie_id": {
                            "type": "integer",
                            "description": "The ID of the movie to get details for"
                        }
                    },
                    "required": ["movie_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_youtube_trailer",
                "description": "Search for and get YouTube trailer video ID for a movie. Use this when the user asks to watch a trailer, see a trailer, or wants to see the movie trailer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "movie_title": {
                            "type": "string",
                            "description": "The title of the movie"
                        },
                        "year": {
                            "type": "integer",
                            "description": "The year the movie was released (optional but helps find the correct trailer)"
                        }
                    },
                    "required": ["movie_title"]
                }
            }
        }
    ]


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'ai-agent',
        'version': '1.0.0',
        'last_heartbeat': last_heartbeat.isoformat()
    }), 200


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        forwarded_for = request.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            user_id = forwarded_for.split(',')[0].strip()
        else:
            user_id = request.remote_addr or 'unknown'

        rate_limit_check = check_rate_limit(user_id)
        if not rate_limit_check.get('allowed', True):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': rate_limit_check.get('message', 'Too many requests'),
                'reset_at': rate_limit_check.get('reset_at'),
                'remaining': 0
            }), 429

        update_activity(user_id)
        send_heartbeat()

        messages = [
            {
                "role": "system",
                "content": """You are a helpful movie recommendation assistant. Your job is to help users find movies they want to watch.

When a user asks about movies:
1. First, ask 1-2 clarifying questions if needed to understand what they want (genre, mood, year, etc.)
2. Use the search_movies function to find relevant movies
3. If movies are found, use get_movie_details to get full information about the most relevant movie(s)
4. Present the movie information in a friendly, conversational way
5. If no movies are found, suggest alternative search terms
6. If the user asks to watch a trailer, see a trailer, or wants to see the movie trailer, use the get_youtube_trailer function with the movie title and year
7. If the user wants to browse all movies or see all available movies, suggest they can browse the full collection

Be conversational, friendly, and helpful. Don't overwhelm users with too many movies at once - focus on 1-3 most relevant ones."""
            }
        ]

        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": msg.get('content', '')
            })

        messages.append({
            "role": "user",
            "content": user_message
        })

        response = client.chat.completions.create(
            model=CURSOR_MODEL,
            messages=messages,
            tools=get_available_functions(),
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )

        assistant_message = response.choices[0].message
        messages.append(assistant_message)

        tool_calls = assistant_message.tool_calls or []
        movie_results = []
        youtube_trailer = None
        movie_detail = None

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            if function_name == "search_movies":
                query = function_args.get('query', '')
                limit = function_args.get('limit', 5)
                movies = search_movies(query, limit)
                movie_results.extend(movies)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "results": movies,
                        "count": len(movies)
                    })
                })

            elif function_name == "get_movie_details":
                movie_id = function_args.get('movie_id')
                movie = get_movie_details(movie_id)
                if movie:
                    movie_detail = movie
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"movie": movie})
                    })

            elif function_name == "get_youtube_trailer":
                movie_title = function_args.get('movie_title', '')
                year = function_args.get('year')
                video_id = search_youtube_trailer(movie_title, year)
                if video_id:
                    youtube_trailer = {
                        'video_id': video_id,
                        'movie_title': movie_title,
                        'year': year
                    }
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "video_id": video_id,
                            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                            "embed_url": f"https://www.youtube.com/embed/{video_id}"
                        })
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "error": "Trailer not found",
                            "message": f"Could not find YouTube trailer for {movie_title}"
                        })
                    })

        if tool_calls:
            final_response = client.chat.completions.create(
                model=CURSOR_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            assistant_message = final_response.choices[0].message

        return jsonify({
            'message': assistant_message.content,
            'movie_results': movie_results,
            'movie_detail': movie_detail,
            'youtube_trailer': youtube_trailer,
            'tool_calls': len(tool_calls) > 0,
            'rate_limit': {
                'remaining': rate_limit_check.get('remaining', 0),
                'reset_at': rate_limit_check.get('reset_at')
            }
        }), 200

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({
            'error': 'An error occurred processing your request',
            'details': str(e)
        }), 500


@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    send_heartbeat()
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


@app.route('/activity/check', methods=['GET'])
def check_activity():
    r = get_redis_client()
    if not r:
        return jsonify({
            'has_activity': False,
            'last_activity': None
        }), 200

    try:
        pattern = "ai_chat_activity:*"
        keys = r.keys(pattern)

        if not keys:
            return jsonify({
                'has_activity': False,
                'last_activity': None
            }), 200

        latest_time = 0
        for key in keys:
            value = r.get(key)
            if value:
                try:
                    timestamp = float(value)
                    latest_time = max(latest_time, timestamp)
                except ValueError:
                    continue

        if latest_time > 0:
            current_time = time.time()
            idle_minutes = (current_time - latest_time) / 60

            return jsonify({
                'has_activity': True,
                'last_activity': latest_time,
                'idle_minutes': round(idle_minutes, 1),
                'should_shutdown': idle_minutes >= AI_CHAT_IDLE_TIMEOUT_MINUTES
            }), 200

        return jsonify({
            'has_activity': False,
            'last_activity': None
        }), 200

    except Exception as e:
        logger.error(f"Activity check failed: {e}")
        return jsonify({
            'has_activity': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    import threading

    def heartbeat_worker():
        while True:
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
            send_heartbeat()

    heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    heartbeat_thread.start()

    app.run(
        host='0.0.0.0',  # nosec B104 - Required for EC2 instance to accept connections
        port=5000,
        debug=False
    )
