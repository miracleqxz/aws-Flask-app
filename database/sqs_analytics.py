import boto3
import json
import time
from config import Config


def send_search_event(query, results_count, cached):
    try:
        sqs = boto3.client('sqs', region_name=Config.AWS_REGION)

        event = {
            'query': query,
            'results_count': results_count,
            'cached': cached,
            'timestamp': time.time()
        }

        response = sqs.send_message(
            QueueUrl=Config.SQS_QUEUE_URL,
            MessageBody=json.dumps(event)
        )

        print(f"Sent to SQS: {query} (MessageId: {response['MessageId']})")
        return True

    except Exception as e:
        print(f"Failed to send to SQS: {e}")
        return False


def get_queue_stats():
    try:
        sqs = boto3.client('sqs', region_name=Config.AWS_REGION)

        response = sqs.get_queue_attributes(
            QueueUrl=Config.SQS_QUEUE_URL,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed'
            ]
        )

        attrs = response['Attributes']

        return {
            'messages_available': int(attrs.get('ApproximateNumberOfMessages', 0)),
            'messages_in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'messages_delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
        }

    except Exception as e:
        print(f"Failed to get queue stats: {e}")
        return None
