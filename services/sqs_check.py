
import boto3
from botocore.exceptions import ClientError
from config import Config


def check_sqs():
    try:
        sqs = boto3.client('sqs', region_name=Config.AWS_REGION)
        
        response = sqs.get_queue_attributes(
            QueueUrl=Config.SQS_QUEUE_URL,
            AttributeNames=['All']
        )
        
        attrs = response['Attributes']
        
        test_message = {'test': 'health-check', 'timestamp': str(__import__('time').time())}
        send_response = sqs.send_message(
            QueueUrl=Config.SQS_QUEUE_URL,
            MessageBody=__import__('json').dumps(test_message)
        )
        
        receive_response = sqs.receive_message(
            QueueUrl=Config.SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1
        )
        
        test_success = False
        if 'Messages' in receive_response:
            for message in receive_response['Messages']:
                sqs.delete_message(
                    QueueUrl=Config.SQS_QUEUE_URL,
                    ReceiptHandle=message['ReceiptHandle']
                )
                test_success = True
        
        return {
            'status': 'healthy',
            'service': 'sqs',
            'message': 'Successfully connected to Amazon SQS',
            'details': {
                'connection': {
                    'region': Config.AWS_REGION,
                    'queue_url': Config.SQS_QUEUE_URL
                },
                'queue': {
                    'name': attrs.get('QueueArn', '').split(':')[-1],
                    'arn': attrs.get('QueueArn', 'N/A'),
                    'created': attrs.get('CreatedTimestamp', 'N/A'),
                    'delay_seconds': attrs.get('DelaySeconds', '0'),
                    'max_message_size': attrs.get('MaximumMessageSize', 'N/A'),
                    'retention_period': attrs.get('MessageRetentionPeriod', 'N/A'),
                    'visibility_timeout': attrs.get('VisibilityTimeout', 'N/A')
                },
                'messages': {
                    'approximate_count': int(attrs.get('ApproximateNumberOfMessages', 0)),
                    'in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
                    'delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
                },
                'test_result': {
                    'send_success': 'MessageId' in send_response,
                    'receive_success': test_success,
                    'delete_success': test_success
                }
            }
        }
        
    except ClientError as e:
        return {
            'status': 'unhealthy',
            'service': 'sqs',
            'message': f'AWS error: {e.response["Error"]["Message"]}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'sqs',
            'message': f'Unexpected error: {str(e)}'
        }