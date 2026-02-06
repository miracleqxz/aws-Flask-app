import requests
from config import Config


def check_nginx():
    try:
        response = requests.get(
            f"http://{Config.NGINX_HOST}:{Config.NGINX_PORT}",
            timeout=5
        )


        status_code = response.status_code
        is_healthy = status_code == 200 or status_code == 404

        server_header = response.headers.get('Server', 'Unknown')
        response_time = response.elapsed.total_seconds()

        return {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'service': 'nginx',
            'message': 'Successfully connected to Nginx',
            'details': {
                'connection': {
                    'host': Config.NGINX_HOST,
                    'port': Config.NGINX_PORT,
                    'url': f"http://{Config.NGINX_HOST}:{Config.NGINX_PORT}"
                },
                'response': {
                    'status_code': status_code,
                    'response_time_seconds': round(response_time, 3),
                    'server_header': server_header
                },
                'headers': {
                    'content_type': response.headers.get('Content-Type', 'N/A'),
                    'content_length': response.headers.get('Content-Length', 'N/A'),
                    'connection': response.headers.get('Connection', 'N/A')
                }
            }
        }

    except requests.ConnectionError as e:
        return {
            'status': 'unhealthy',
            'service': 'nginx',
            'message': f'Connection error: {str(e)}'
        }
    except requests.Timeout as e:
        return {
            'status': 'unhealthy',
            'service': 'nginx',
            'message': f'Timeout error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'nginx',
            'message': f'Unexpected error: {str(e)}'
        }
