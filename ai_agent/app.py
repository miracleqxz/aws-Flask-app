#!/usr/bin/env python3
import os
import json
import logging
import threading
import time
from datetime import datetime, timezone

import redis
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- Required env vars ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")

GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

client = genai.Client(api_key=GEMINI_API_KEY)

MOVIE_API_BASE_URL = os.getenv('MOVIE_API_BASE_URL')
if not MOVIE_API_BASE_URL:
    raise ValueError("MOVIE_API_BASE_URL environment variable is required")

LAMBDA_API_URL = os.getenv('LAMBDA_API_URL', '')
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv('HEARTBEAT_INTERVAL_SECONDS', '30'))

REDIS_HOST = os.getenv('REDIS_HOST')
if not REDIS_HOST:
    raise ValueError("REDIS_HOST environment variable is required")

REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

MEILISEARCH_HOST = os.getenv('MEILISEARCH_HOST')
if not MEILISEARCH_HOST:
    raise ValueError("MEILISEARCH_HOST environment variable is required")

MEILISEARCH_PORT = os.getenv('MEILISEARCH_PORT', '7700')

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')

AI_CHAT_MAX_REQUESTS = int(os.getenv('AI_CHAT_MAX_REQUESTS', '10'))
AI_CHAT_WINDOW_SECONDS = int(os.getenv('AI_CHAT_WINDOW_SECONDS', '60'))
AI_CHAT_DAILY_LIMIT = int(os.getenv('AI_CHAT_DAILY_LIMIT', '100'))
AI_CHAT_IDLE_TIMEOUT_MINUTES = int(os.getenv('AI_CHAT_IDLE_TIMEOUT_MINUTES', '5'))

MAX_TOOL_CALL_ROUNDS = 5

# --- Redis connection pool (single pool, reused across requests) ---
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True,
    socket_timeout=5,
    max_connections=20
)


def get_redis_client():
    try:
        return redis.Redis(connection_pool=redis_pool)
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


# --- Thread-safe heartbeat tracking ---
_heartbeat_lock = threading.Lock()
_last_heartbeat = datetime.now(timezone.utc)


def get_last_heartbeat():
    with _heartbeat_lock:
        return _last_heartbeat


def send_heartbeat():
    global _last_heartbeat
    if not LAMBDA_API_URL:
        return

    try:
        response = requests.post(
            f"{LAMBDA_API_URL}/heartbeat",
            timeout=5
        )
        if response.status_code == 200:
            with _heartbeat_lock:
                _last_heartbeat = datetime.now(timezone.utc)
            logger.info("Heartbeat sent successfully")
        else:
            logger.warning(f"Heartbeat failed with status {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending heartbeat: {e}")


# --- Rate limiter with Lua script (atomic) ---
RATE_LIMIT_LUA = """
local short_key = KEYS[1]
local daily_key = KEYS[2]

local max_requests = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_daily_requests = tonumber(ARGV[3])
local daily_window = tonumber(ARGV[4])
local now = tonumber(ARGV[5])

-- Check short-term limit
redis.call('ZREMRANGEBYSCORE', short_key, 0, now - window)
local short_count = redis.call('ZCARD', short_key)

if short_count >= max_requests then
    local oldest = redis.call('ZRANGE', short_key, 0, 0, 'WITHSCORES')
    local reset_at = 0
    if #oldest > 0 then
        reset_at = tonumber(oldest[2]) + window
    end
    return {0, 0, reset_at, 'minute'}
end

-- Check daily limit
redis.call('ZREMRANGEBYSCORE', daily_key, 0, now - daily_window)
local daily_count = redis.call('ZCARD', daily_key)

if daily_count >= max_daily_requests then
    local oldest = redis.call('ZRANGE', daily_key, 0, 0, 'WITHSCORES')
    local reset_at = 0
    if #oldest > 0 then
        reset_at = tonumber(oldest[2]) + daily_window
    end
    return {0, 0, reset_at, 'daily'}
end

-- If both pass, record the request in both windows
local req_id = tostring(now) .. ':' .. tostring(math.random(100000))
redis.call('ZADD', short_key, now, req_id)
redis.call('EXPIRE', short_key, window)

redis.call('ZADD', daily_key, now, req_id)
redis.call('EXPIRE', daily_key, daily_window)

local remaining = max_requests - short_count - 1
return {1, remaining, now + window, 'ok'}
"""


def check_rate_limit(user_id):
    r = get_redis_client()
    if not r:
        return {'allowed': True, 'remaining': AI_CHAT_MAX_REQUESTS}

    short_key = f"ai_chat_rate_limit:{user_id}"
    daily_key = f"ai_chat_daily_limit:{user_id}"
    current_time = time.time()
    
    # 24 hours in seconds
    daily_window = 24 * 60 * 60

    try:
        result = r.eval(
            RATE_LIMIT_LUA, 2, short_key, daily_key,
            AI_CHAT_MAX_REQUESTS, AI_CHAT_WINDOW_SECONDS, 
            AI_CHAT_DAILY_LIMIT, daily_window, current_time
        )

        allowed = int(result[0]) == 1
        remaining = max(0, int(result[1]))
        reset_at = int(result[2])
        limit_type = result[3]

        if not allowed:
            remaining_seconds = reset_at - int(current_time)
            msg = f'Rate limit exceeded. Try again in {remaining_seconds} seconds.'
            if limit_type == 'daily':
                hours = remaining_seconds // 3600
                mins = (remaining_seconds % 3600) // 60
                msg = f'Daily limit reached ({AI_CHAT_DAILY_LIMIT} messages). Try again in {hours}h {mins}m.'
            
            return {
                'allowed': False,
                'remaining': 0,
                'reset_at': reset_at,
                'message': msg
            }

        return {
            'allowed': True,
            'remaining': remaining,
            'reset_at': reset_at
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


# --- Movie API functions ---
def search_movies(query, limit=10):
    try:
        logger.info(f"Searching movies: query='{query}', limit={limit}")
        response = requests.get(
            f"{MOVIE_API_BASE_URL}/api/search",
            params={'q': query, 'limit': limit},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            logger.info(f"Search returned {len(results)} results for query='{query}'")
            return results
        logger.error(f"Search API returned {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error searching movies: {e}")
        return []


def get_movie_details(movie_id):
    try:
        response = requests.get(
            f"{MOVIE_API_BASE_URL}/api/movie/{movie_id}",
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


# --- Tool definitions ---
def get_available_functions():
    return [
        {
            "name": "search_movies",
            "description": "Search for movies in the database by keywords, genre, mood, or description. Use this when the user wants to find movies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in ENGLISH - genre name, mood keyword, actor, director, or movie title"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)"
                    }
                },
                "required": ["query"]
            }
        },
        {
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
        },
        {
            "name": "get_youtube_trailer",
            "description": "Search for and get YouTube trailer video ID for a movie. Use this when the user asks to watch a trailer, see a trailer, or wants to see the movie trailer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_title": {
                        "type": "string",
                        "description": "The original English title of the movie"
                    },
                    "year": {
                        "type": "integer",
                        "description": "The year the movie was released (optional but helps find the correct trailer)"
                    }
                },
                "required": ["movie_title"]
            }
        }
    ]


SYSTEM_INSTRUCTION = """You are Guidy — a friendly movie assistant for a curated film database.

PERSONALITY:
- Talk like a real person texting a friend. Short sentences. Casual tone.
- No bullet points, no numbered lists, no walls of text.
- 1-3 sentences max per response. Be brief.
- Use the same language the user writes in.

IMPORTANT: You can ONLY discuss movies and film topics. For anything else, say you're a movie assistant and suggest they ask about films instead.

CRITICAL — DATABASE ONLY:
- You MUST call search_movies BEFORE mentioning ANY movie. NEVER recommend or confirm a movie without searching first.
- Even if the user asks for a specific movie by name (e.g. "die hard"), you MUST call search_movies for it immediately. If you do not call the search tool, the user's screen will go blank.
- ONLY present movies that appear in search results.
- When you mention a movie from the search results, YOU MUST include its original English title exactly as it appears in the results, enclosed in brackets. Example: [The Matrix].
- If the user asks for a specific movie and it is not found, tell them it is not in the database and search for alternatives.
- Keep it casual: just the title and a brief comment. Do not repeat rating, year, genre info.

FUNCTION CALLING:
- Translate non-English input to English before searching. Examples: "комедии" → "comedy", "Начало" → "Inception".
- Use 1-3 English keywords per search. Keep it short.
- Map moods to keywords: "something light" → "comedy", "scary" → "horror", "cry" → "drama".
- If no results, try synonyms once, then tell the user.
- Call get_movie_details for specific movie info.
- Call get_youtube_trailer when user wants a trailer.
- If vague request, ask ONE short question before searching.

EXAMPLES OF GOOD RESPONSES:
- "Here are a few comedies from our collection — take a look!"
- "The Dark Knight is right here 👆 Great pick!"
- "Hmm, we don't have that one yet. But check out these similar thrillers!"
- "What kind of mood? Something dark or more lighthearted?"

EXAMPLES OF BAD RESPONSES (NEVER DO THIS):
- Long paragraphs describing each movie
- Numbered lists with ratings and descriptions
- Mentioning movies you haven't searched for
- Repeating info the UI already shows (rating, year, genre)"""


def execute_tool_call(tool_call, movie_results, youtube_trailer_holder, movie_detail_holder):
    """Execute a single tool call and return a function response Part."""
    function_name = tool_call.name
    function_args = {}
    if hasattr(tool_call, 'args'):
        if isinstance(tool_call.args, dict):
            function_args = tool_call.args
        else:
            try:
                function_args = dict(tool_call.args)
            except (TypeError, ValueError):
                function_args = {}

    if function_name == "search_movies":
        query = function_args.get('query', '')
        limit = function_args.get('limit', 5)
        movies = search_movies(query, limit)
        movie_results.extend(movies)
        return types.Part.from_function_response(
            name=function_name,
            response={"results": movies, "count": len(movies)}
        )

    elif function_name == "get_movie_details":
        movie_id = function_args.get('movie_id')
        movie = get_movie_details(movie_id)
        if movie:
            movie_detail_holder.append(movie)
            return types.Part.from_function_response(
                name=function_name,
                response={"movie": movie}
            )
        else:
            return types.Part.from_function_response(
                name=function_name,
                response={"error": "Movie not found", "movie_id": movie_id}
            )

    elif function_name == "get_youtube_trailer":
        movie_title = function_args.get('movie_title', '')
        year = function_args.get('year')
        video_id = search_youtube_trailer(movie_title, year)
        if video_id:
            youtube_trailer_holder.append({
                'video_id': video_id,
                'movie_title': movie_title,
                'year': year
            })
            return types.Part.from_function_response(
                name=function_name,
                response={
                    "video_id": video_id,
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "embed_url": f"https://www.youtube.com/embed/{video_id}"
                }
            )
        else:
            return types.Part.from_function_response(
                name=function_name,
                response={
                    "error": "Trailer not found",
                    "message": f"Could not find YouTube trailer for {movie_title}"
                }
            )

    return None


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'ai-agent',
        'version': '1.0.0',
        'last_heartbeat': get_last_heartbeat().isoformat()
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

        tools = types.Tool(function_declarations=get_available_functions())
        config = types.GenerateContentConfig(
            tools=[tools],
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
            max_output_tokens=1000
        )

        contents = []
        for msg in conversation_history[-10:]:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
            elif role == 'assistant':
                contents.append(types.Content(role="model", parts=[types.Part(text=content)]))

        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        # Accumulators for structured response data
        movie_results = []
        youtube_trailer_holder = []
        movie_detail_holder = []
        assistant_message_content = ""
        total_tool_calls = 0

        # Multi-round tool call loop
        for round_num in range(MAX_TOOL_CALL_ROUNDS):
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config
            )

            if not response.candidates or not response.candidates[0].content:
                break

            # Extract tool calls and text from response
            tool_calls = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tool_calls.append(part.function_call)
                elif hasattr(part, 'text') and part.text:
                    assistant_message_content = part.text

            if not tool_calls:
                break

            total_tool_calls += len(tool_calls)
            logger.info(f"Tool call round {round_num + 1}: {[tc.name for tc in tool_calls]}")

            # Append model's response with function calls
            contents.append(response.candidates[0].content)

            # Execute all tool calls and collect responses
            function_response_parts = []
            for tool_call in tool_calls:
                part = execute_tool_call(
                    tool_call, movie_results,
                    youtube_trailer_holder, movie_detail_holder
                )
                if part:
                    function_response_parts.append(part)

            if function_response_parts:
                contents.append(types.Content(role="user", parts=function_response_parts))
            else:
                break

        # If we exited the loop after tool calls, get final text response
        if total_tool_calls > 0 and not assistant_message_content:
            final_response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config
            )
            if final_response.candidates and final_response.candidates[0].content:
                for part in final_response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        assistant_message_content = part.text

        return jsonify({
            'message': assistant_message_content,
            'movie_results': movie_results,
            'movie_detail': movie_detail_holder[-1] if movie_detail_holder else None,
            'youtube_trailer': youtube_trailer_holder[-1] if youtube_trailer_holder else None,
            'tool_calls': total_tool_calls > 0,
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
        latest_time = 0.0
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match="ai_chat_activity:*", count=100)
            for key in keys:
                value = r.get(key)
                if value:
                    try:
                        latest_time = max(latest_time, float(value))
                    except ValueError:
                        continue
            if cursor == 0:
                break

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
    def heartbeat_worker():
        while True:
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
            send_heartbeat()

    heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    heartbeat_thread.start()

    app.run(
        host='0.0.0.0',  # nosec B104 - Required for container/EC2 to accept connections
        port=int(os.getenv('AI_AGENT_PORT', '5001')),
        debug=False
    )