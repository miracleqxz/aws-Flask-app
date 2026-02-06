import redis
import json
from config import Config


def get_redis_client():
    return redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        decode_responses=True
    )


def cache_key(query):
    normalized = query.lower().strip()
    return f"search:{normalized}"


def get_cached_search(query):
    client = get_redis_client()
    key = cache_key(query)

    try:
        cached = client.get(key)
        if cached:
            return json.loads(cached)
        return None
    except Exception as e:
        print(f"Redis get error: {e}")
        return None


def set_cached_search(query, results, ttl=300):
    client = get_redis_client()
    key = cache_key(query)

    try:
        client.setex(
            key,
            ttl,
            json.dumps(results)
        )
    except Exception as e:
        print(f"Redis set error: {e}")


def clear_search_cache():
    client = get_redis_client()

    try:
        keys = client.keys("search:*")
        if keys:
            client.delete(*keys)
            return len(keys)
        return 0
    except Exception as e:
        print(f"Redis clear error: {e}")
        return 0


def get_cache_stats():
    client = get_redis_client()

    try:
        info = client.info('stats')
        return {
            'hits': info.get('keyspace_hits', 0),
            'misses': info.get('keyspace_misses', 0),
            'keys_count': client.dbsize()
        }
    except Exception as e:
        print(f"Redis stats error: {e}")
        return None
