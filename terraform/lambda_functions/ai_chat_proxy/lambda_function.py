import json
import os
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AI_AGENT_FLASK_URL = os.environ.get('AI_AGENT_FLASK_URL', 'https://localhost:5000')
API_KEY = os.environ.get('API_KEY', '')

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Api-Key'
}


def _build_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body) if isinstance(body, dict) else body
    }


def _proxy_get(path, timeout=5):
    url = f"{AI_AGENT_FLASK_URL}{path}"
    req = Request(url, method='GET')

    with urlopen(req, timeout=timeout) as response:
        return response.status, response.read().decode('utf-8')


def _proxy_post(path, body, headers=None, timeout=60):
    url = f"{AI_AGENT_FLASK_URL}{path}"
    data = json.dumps(body).encode('utf-8') if isinstance(body, dict) else body.encode('utf-8')

    req = Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')

    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    with urlopen(req, timeout=timeout) as response:
        return response.status, response.read().decode('utf-8')


def handler(event, context):
    logger.info(f"Received event path: {event.get('rawPath', event.get('path', 'unknown'))}")

    if 'requestContext' not in event:
        return _build_response(400, {'error': 'Invalid request'})

    path = event.get('rawPath') or event.get('path', '')
    method = (
        event.get('requestContext', {}).get('http', {}).get('method')
        or event.get('requestContext', {}).get('httpMethod')
        or event.get('httpMethod', 'GET')
    )

    # API key validation
    api_key_header = (
        event.get('headers', {}).get('x-api-key')
        or event.get('headers', {}).get('X-Api-Key', '')
    )
    if API_KEY and api_key_header != API_KEY:
        return _build_response(401, {'error': 'Invalid API key'})

    try:
        if path == '/chat' and method == 'POST':
            body = event.get('body', '{}')
            if isinstance(body, str):
                body = json.loads(body)

            proxy_headers = {}
            if 'headers' in event:
                forwarded_for = (
                    event['headers'].get('x-forwarded-for')
                    or event['headers'].get('X-Forwarded-For', '')
                )
                if forwarded_for:
                    proxy_headers['X-Forwarded-For'] = forwarded_for.split(',')[0].strip()

            status, response_body = _proxy_post('/chat', body, proxy_headers, timeout=60)
            return _build_response(status, json.loads(response_body))

        elif path == '/health' and method == 'GET':
            status, response_body = _proxy_get('/health')
            return _build_response(status, json.loads(response_body))

        elif path == '/activity/check' and method == 'GET':
            status, response_body = _proxy_get('/activity/check')
            return _build_response(status, json.loads(response_body))

        else:
            return _build_response(404, {'error': 'Not found'})

    except HTTPError as e:
        logger.error(f"Upstream HTTP error: {e.code} {e.reason}")
        return _build_response(e.code, {
            'error': 'Upstream error',
            'details': f"{e.code} {e.reason}"
        })

    except URLError as e:
        logger.error(f"AI Agent unreachable: {e.reason}")
        return _build_response(503, {
            'error': 'AI Agent service unavailable',
            'details': str(e.reason)
        })

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return _build_response(500, {
            'error': 'Internal server error',
            'details': str(e)
        })
