import requests
from config import Config


def check_grafana():
    try:
        health_url = f"http://{Config.GRAFANA_HOST}:{Config.GRAFANA_PORT}/api/health"
        
        response = requests.get(health_url, timeout=5)
        
        is_healthy = response.status_code == 200
        
        if is_healthy:
            health_data = response.json()
        else:
            health_data = {}
        
        try:
            version_url = f"http://{Config.GRAFANA_HOST}:{Config.GRAFANA_PORT}/api/health"
            version_response = requests.get(version_url, timeout=5)
            version_info = version_response.json() if version_response.status_code == 200 else {}
        except:
            version_info = {}
        
        response_time = response.elapsed.total_seconds()
        
        return {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'service': 'grafana',
            'message': 'Successfully connected to Grafana',
            'details': {
                'connection': {
                    'host': Config.GRAFANA_HOST,
                    'port': Config.GRAFANA_PORT,
                    'health_endpoint': health_url
                },
                'health': {
                    'status': health_data.get('database', 'unknown'),
                    'version': health_data.get('version', 'N/A'),
                    'commit': health_data.get('commit', 'N/A')
                },
                'response': {
                    'status_code': response.status_code,
                    'response_time_seconds': round(response_time, 3)
                },
                'info': version_info
            }
        }
        
    except requests.ConnectionError as e:
        return {
            'status': 'unhealthy',
            'service': 'grafana',
            'message': f'Connection error: {str(e)}'
        }
    except requests.Timeout as e:
        return {
            'status': 'unhealthy',
            'service': 'grafana',
            'message': f'Timeout error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'grafana',
            'message': f'Unexpected error: {str(e)}'
        }