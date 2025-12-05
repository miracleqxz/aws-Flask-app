"""Redis caching for search results"""
import redis
import json
from config import Config


def get_redis_client():
    """Create Redis client"""
    return redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        decode_responses=True  # Auto-decode bytes to strings
    )


def cache_key(query):
    """Generate cache key from search query"""
    # Normalize: lowercase + trim
    normalized = query.lower().strip()
    return f"search:{normalized}"


def get_cached_search(query):
    """
    Get cached search results
    
    Args:
        query: search string
    
    Returns:
        list: cached results or None
    """
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
    """
    Cache search results
    
    Args:
        query: search string
        results: list of movie dicts
        ttl: time to live in seconds (default 5 min)
    """
    client = get_redis_client()
    key = cache_key(query)
    
    try:
        # Store as JSON
        client.setex(
            key,
            ttl,
            json.dumps(results)
        )
    except Exception as e:
        print(f"Redis set error: {e}")


def clear_search_cache():
    """Clear all search cache"""
    client = get_redis_client()
    
    try:
        # Find all search keys
        keys = client.keys("search:*")
        if keys:
            client.delete(*keys)
            return len(keys)
        return 0
    except Exception as e:
        print(f"Redis clear error: {e}")
        return 0


def get_cache_stats():
    """Get cache statistics"""
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
