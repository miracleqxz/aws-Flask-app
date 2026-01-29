import redis
import json
from config import Config
from decimal import Decimal


def get_redis_client():
    return redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        decode_responses=True
    )


def serialize_movie(movie_data):
    serialized = {}
    for key, value in movie_data.items():
        if isinstance(value, Decimal):
            serialized[key] = float(value)
        else:
            serialized[key] = value
    return serialized


def get_cached_movie(movie_id):
    client = get_redis_client()
    key = f"movie:{movie_id}"
    
    try:
        cached = client.get(key)
        print(f"Redis GET {key}: {cached is not None}")  
        
        if cached:
            movie_data = json.loads(cached)
            print(f"Found in cache: {movie_data.get('title')}")  
            return movie_data, True
        
        print(f"Not in cache")  
        return None, False
    except Exception as e:
        print(f"Redis get error: {e}")
        return None, False


def set_cached_movie(movie_id, movie_data, ttl=600):
    client = get_redis_client()
    key = f"movie:{movie_id}"
    
    try:
        serialized = serialize_movie(movie_data)
        json_data = json.dumps(serialized)
        
        result = client.setex(key, ttl, json_data)
        
        print(f"Redis SET {key}: {result}")  
        print(f"Data: {json_data[:100]}...")  
        
        return result
    except Exception as e:
        print(f"Redis set error: {e}")
        return False


def clear_movie_cache(movie_id=None):
    client = get_redis_client()
    
    try:
        if movie_id:
            key = f"movie:{movie_id}"
            client.delete(key)
            return 1
        else:
            keys = client.keys("movie:*")
            if keys:
                client.delete(*keys)
                return len(keys)
            return 0
    except Exception as e:
        print(f"Redis clear error: {e}")
        return 0

