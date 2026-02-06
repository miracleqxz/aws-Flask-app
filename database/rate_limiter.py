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


def check_rate_limit(action: str, cooldown_seconds: int = 300) -> dict:
    r = get_redis_client()
    if not r:
        logger.warning("Rate limiter: Redis unavailable, allowing action")
        return {'allowed': True, 'retry_after': 0, 'message': 'ok'}

    key = f"rate_limit:{action}"

    try:
        last_call = r.get(key)

        if last_call:
            last_call_time = float(last_call)
            elapsed = time.time() - last_call_time
            remaining = cooldown_seconds - elapsed

            if remaining > 0:
                return {
                    'allowed': False,
                    'retry_after': int(remaining),
                    'message': f'Rate limited. Try again in {int(remaining)} seconds.'
                }

        r.setex(key, cooldown_seconds, str(time.time()))

        return {'allowed': True, 'retry_after': 0, 'message': 'ok'}

    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return {'allowed': True, 'retry_after': 0, 'message': 'ok'}


def get_rate_limit_status(action: str, cooldown_seconds: int = 300) -> dict:
    r = get_redis_client()
    if not r:
        return {'available': True, 'retry_after': 0}

    key = f"rate_limit:{action}"

    try:
        last_call = r.get(key)

        if last_call:
            last_call_time = float(last_call)
            elapsed = time.time() - last_call_time
            remaining = cooldown_seconds - elapsed

            if remaining > 0:
                return {'available': False, 'retry_after': int(remaining)}

        return {'available': True, 'retry_after': 0}

    except Exception as e:
        logger.error(f"Rate limit status check failed: {e}")
        return {'available': True, 'retry_after': 0}
