import redis
import time
import logging
from config import Config

logger = logging.getLogger(__name__)


def get_redis_client():
    try:
        return redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=0,
            decode_responses=True,
            socket_timeout=5
        )
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


def check_ai_chat_rate_limit(user_id: str, max_requests: int = 10, window_seconds: int = 60) -> dict:
    r = get_redis_client()
    if not r:
        logger.warning("Rate limiter: Redis unavailable, allowing action")
        return {
            'allowed': True,
            'remaining': max_requests,
            'reset_at': int(time.time()) + window_seconds,
            'message': 'ok'
        }

    key = f"ai_chat_rate_limit:{user_id}"

    try:
        current_time = time.time()

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, current_time - window_seconds)
        pipe.zcard(key)
        pipe.zadd(key, {str(current_time): current_time})
        pipe.expire(key, window_seconds)
        results = pipe.execute()

        current_count = results[1]

        if current_count >= max_requests:
            oldest_request = r.zrange(key, 0, 0, withscores=True)
            if oldest_request:
                reset_time = int(oldest_request[0][1] + window_seconds)
                remaining_seconds = reset_time - int(current_time)

                return {
                    'allowed': False,
                    'remaining': 0,
                    'reset_at': reset_time,
                    'message': f'Rate limit exceeded. Try again in {remaining_seconds} seconds.'
                }

        remaining = max_requests - current_count - 1
        reset_at = int(current_time) + window_seconds

        return {
            'allowed': True,
            'remaining': max(0, remaining),
            'reset_at': reset_at,
            'message': 'ok'
        }

    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return {
            'allowed': True,
            'remaining': max_requests,
            'reset_at': int(time.time()) + window_seconds,
            'message': 'ok'
        }


def update_ai_chat_activity(user_id: str, activity_ttl: int = 300):
    r = get_redis_client()
    if not r:
        return

    key = f"ai_chat_activity:{user_id}"

    try:
        r.setex(key, activity_ttl, str(time.time()))
    except Exception as e:
        logger.error(f"Failed to update activity: {e}")


def get_last_ai_chat_activity() -> float:
    r = get_redis_client()
    if not r:
        return 0

    try:
        pattern = "ai_chat_activity:*"
        keys = r.keys(pattern)

        if not keys:
            return 0

        latest_time = 0
        for key in keys:
            value = r.get(key)
            if value:
                try:
                    timestamp = float(value)
                    latest_time = max(latest_time, timestamp)
                except ValueError:
                    continue

        return latest_time
    except Exception as e:
        logger.error(f"Failed to get last activity: {e}")
        return 0
