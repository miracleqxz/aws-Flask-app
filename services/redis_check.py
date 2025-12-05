
import redis
from config import Config


def check_redis():
    try:
        client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            socket_connect_timeout=5,
            decode_responses=True
        )
        
        
        pong = client.ping()
        
        info = client.info()
        
        # Database size (keys count)
        db_size = client.dbsize()
        
        
        memory_used = info['used_memory_human']
        memory_peak = info['used_memory_peak_human']
        memory_rss = info.get('used_memory_rss_human', 'N/A')
        
        
        connected_clients = info['connected_clients']
        blocked_clients = info.get('blocked_clients', 0)
        
        
        uptime_seconds = info['uptime_in_seconds']
        uptime_days = uptime_seconds // 86400
        uptime_hours = (uptime_seconds % 86400) // 3600
        uptime_str = f"{uptime_days}d {uptime_hours}h"
        
        
        total_commands = info['total_commands_processed']
        instantaneous_ops = info.get('instantaneous_ops_per_sec', 0)
        
        
        keyspace_hits = info.get('keyspace_hits', 0)
        keyspace_misses = info.get('keyspace_misses', 0)
        total_keyspace_ops = keyspace_hits + keyspace_misses
        hit_rate = round((keyspace_hits / total_keyspace_ops) * 100, 2) if total_keyspace_ops > 0 else 0
        
        # Key analysis by type
        search_keys = len(client.keys('search:*'))
        movie_keys = len(client.keys('movie:*'))
        other_keys = db_size - search_keys - movie_keys
        
        # Evicted keys (memory pressure indicator)
        evicted_keys = info.get('evicted_keys', 0)
        
        # Persistence
        rdb_last_save_time = info.get('rdb_last_save_time', 0)
        rdb_changes_since_last_save = info.get('rdb_changes_since_last_save', 0)
        
        client.close()
        
        return {
            'status': 'healthy',
            'service': 'redis',
            'message': 'Successfully connected to Redis',
            'details': {
                'connection': {
                    'host': Config.REDIS_HOST,
                    'port': Config.REDIS_PORT,
                    'connected_clients': connected_clients,
                    'blocked_clients': blocked_clients
                },
                'version': info['redis_version'],
                'uptime': uptime_str,
                'memory': {
                    'used': memory_used,
                    'peak': memory_peak,
                    'rss': memory_rss,
                    'fragmentation_ratio': info.get('mem_fragmentation_ratio', 'N/A'),
                    'evicted_keys': evicted_keys
                },
                'data': {
                    'total_keys': db_size,
                    'search_cache_keys': search_keys,
                    'movie_cache_keys': movie_keys,
                    'other_keys': other_keys
                },
                'performance': {
                    'total_commands_processed': total_commands,
                    'instantaneous_ops_per_sec': instantaneous_ops,
                    'keyspace_hits': keyspace_hits,
                    'keyspace_misses': keyspace_misses,
                    'hit_rate_percent': hit_rate
                },
                'persistence': {
                    'rdb_last_save_time': rdb_last_save_time,
                    'rdb_changes_since_last_save': rdb_changes_since_last_save
                }
            }
        }
        
    except redis.ConnectionError as e:
        return {
            'status': 'unhealthy',
            'service': 'redis',
            'message': f'Connection error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'redis',
            'message': f'Unexpected error: {str(e)}'
        }
