import requests
from config import Config


def check_meilisearch():
    try:
        base_url = f"http://{Config.MEILISEARCH_HOST}:{Config.MEILISEARCH_PORT}"
      
        health_response = requests.get(f"{base_url}/health", timeout=5)
        health_data = health_response.json()
        
        version_response = requests.get(f"{base_url}/version", timeout=5)
        version_data = version_response.json()
        
        stats_response = requests.get(f"{base_url}/stats", timeout=5)
        stats_data = stats_response.json()
        
        indexes_response = requests.get(f"{base_url}/indexes", timeout=5)
        indexes_data = indexes_response.json()
        
        movies_index_exists = any(idx['uid'] == 'movies' for idx in indexes_data['results'])
        
        movies_details = None
        if movies_index_exists:
            movies_response = requests.get(f"{base_url}/indexes/movies", timeout=5)
            movies_details = movies_response.json()
        
        return {
            'status': 'healthy',
            'service': 'meilisearch',
            'message': 'Successfully connected to Meilisearch',
            'details': {
                'connection': {
                    'host': Config.MEILISEARCH_HOST,
                    'port': Config.MEILISEARCH_PORT,
                    'url': base_url
                },
                'health': health_data,
                'version': {
                    'package_version': version_data.get('pkgVersion', 'N/A'),
                    'commit_sha': version_data.get('commitSha', 'N/A')[:8],
                    'commit_date': version_data.get('commitDate', 'N/A')
                },
                'stats': {
                    'database_size': stats_data.get('databaseSize', 0),
                    'last_update': stats_data.get('lastUpdate', 'N/A')
                },
                'indexes': {
                    'total_count': len(indexes_data['results']),
                    'movies_index_exists': movies_index_exists,
                    'movies_documents': movies_details.get('numberOfDocuments', 0) if movies_details else 0
                }
            }
        }
        
    except requests.Timeout:
        return {
            'status': 'unhealthy',
            'service': 'meilisearch',
            'message': 'Connection timeout'
        }
    except requests.ConnectionError as e:
        return {
            'status': 'unhealthy',
            'service': 'meilisearch',
            'message': f'Connection error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'meilisearch',
            'message': f'Unexpected error: {str(e)}'
        }