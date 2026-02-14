import json
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client('ec2')

BACKEND_INSTANCE_ID = os.environ['BACKEND_INSTANCE_ID']
AI_AGENT_INSTANCE_ID = os.environ['AI_AGENT_INSTANCE_ID']
INSTANCE_IDS = [BACKEND_INSTANCE_ID, AI_AGENT_INSTANCE_ID]


def get_states():
    resp = ec2.describe_instances(InstanceIds=INSTANCE_IDS)
    result = {}
    for res in resp['Reservations']:
        for inst in res['Instances']:
            result[inst['InstanceId']] = {
                'state': inst['State']['Name'],
                'ip': inst.get('PublicIpAddress', '')
            }
    return result


def start_all():
    states = get_states()
    to_start = [iid for iid in INSTANCE_IDS if states.get(iid, {}).get('state') == 'stopped']
    if to_start:
        ec2.start_instances(InstanceIds=to_start)
        logger.info(f"Started: {to_start}")
    return {'action': 'start', 'started': to_start, 'states': states}


def stop_all():
    states = get_states()
    to_stop = [iid for iid in INSTANCE_IDS if states.get(iid, {}).get('state') == 'running']
    if to_stop:
        ec2.stop_instances(InstanceIds=to_stop)
        logger.info(f"Stopped: {to_stop}")
    return {'action': 'stop', 'stopped': to_stop, 'states': states}


def handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    action = event.get('action', 'status')

    if event.get('source') == 'aws.events':
        for r in event.get('resources', []):
            if ':rule/' in r:
                rule = r.split(':rule/')[-1].lower()
                action = 'start' if 'start' in rule else 'stop' if 'stop' in rule else 'status'

    if 'requestContext' in event:
        path = event.get('rawPath', '')
        if '/start' in path: action = 'start'
        elif '/stop' in path: action = 'stop'

    if action == 'start':
        result = start_all()
    elif action == 'stop':
        result = stop_all()
    else:
        result = {'states': get_states()}

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(result, default=str)
    }
