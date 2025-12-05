
import requests
from config import Config


def check_prometheus():
    try:
        base_url = f"http://{Config.PROMETHEUS_HOST}:{Config.PROMETHEUS_PORT}"
        
        
        health_url = f"{base_url}/-/healthy"
        health_response = requests.get(health_url, timeout=5)
        
        if health_response.status_code != 200:
            return {
                'status': 'unhealthy',
                'service': 'prometheus',
                'message': f'Health check failed: status {health_response.status_code}'
            }
        
        
        ready_url = f"{base_url}/-/ready"
        ready_response = requests.get(ready_url, timeout=5)
        is_ready = ready_response.status_code == 200
        
        
        buildinfo_url = f"{base_url}/api/v1/status/buildinfo"
        build_response = requests.get(buildinfo_url, timeout=5)
        build_data = build_response.json()
        
        
        runtimeinfo_url = f"{base_url}/api/v1/status/runtimeinfo"
        runtime_response = requests.get(runtimeinfo_url, timeout=5)
        runtime_data = runtime_response.json()
        
        
        targets_url = f"{base_url}/api/v1/targets"
        targets_response = requests.get(targets_url, timeout=5)
        targets_data = targets_response.json()
        
        active_targets = targets_data['data']['activeTargets']
        healthy_targets = sum(1 for t in active_targets if t['health'] == 'up')
        
        # Query test - get up metric
        query_url = f"{base_url}/api/v1/query"
        query_response = requests.get(query_url, params={'query': 'up'}, timeout=5)
        query_data = query_response.json()
        
        # Get all metric names
        labels_url = f"{base_url}/api/v1/label/__name__/values"
        labels_response = requests.get(labels_url, timeout=5)
        labels_data = labels_response.json()
        total_metrics = len(labels_data['data'])
        
        return {
            'status': 'healthy',
            'service': 'prometheus',
            'message': 'Successfully connected to Prometheus',
            'details': {
                'connection': {
                    'endpoint': base_url,
                    'ready': is_ready
                },
                'version': {
                    'version': build_data['data']['version'],
                    'go_version': build_data['data'].get('goVersion', 'N/A'),
                    'build_date': build_data['data'].get('buildDate', 'N/A')
                },
                'runtime': {
                    'start_time': runtime_data['data'].get('startTime', 'N/A'),
                    'storage_retention': runtime_data['data'].get('storageRetention', 'N/A')
                },
                'targets': {
                    'total_targets': len(active_targets),
                    'healthy_targets': healthy_targets,
                    'unhealthy_targets': len(active_targets) - healthy_targets,
                    'target_details': [
                        {
                            'job': t.get('labels', {}).get('job', 'N/A'),
                            'instance': t.get('labels', {}).get('instance', 'N/A'),
                            'health': t.get('health', 'N/A'),
                            'last_scrape': t.get('lastScrape', 'N/A')
                        }
                        for t in active_targets[:5]  # Limit to first 5
                    ]
                },
                'metrics': {
                    'total_metrics': total_metrics
                },
                'query_test': {
                    'query': 'up',
                    'result_type': query_data['data']['resultType'],
                    'results_count': len(query_data['data']['result'])
                }
            }
        }
        
    except requests.exceptions.RequestException as e:
        return {
            'status': 'unhealthy',
            'service': 'prometheus',
            'message': f'Request error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'prometheus',
            'message': f'Unexpected error: {str(e)}'
        }
