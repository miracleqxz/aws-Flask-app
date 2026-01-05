import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config


def check_sqs():
    try:
        sqs = boto3.client(
            'sqs',
            region_name=Config.AWS_REGION
        )
        
        queue_url = Config.SQS_QUEUE_URL
        
        if not queue_url:
            return {
                'status': 'unhealthy',
                'service': 'sqs',
                'message': 'SQS_QUEUE_URL not configured'
            }
        
        # Get queue attributes
        attributes_response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        )
        
        attributes = attributes_response.get('Attributes', {})
        
        # Extract queue name from URL
        queue_name = queue_url.split('/')[-1]
        
        # Get approximate message counts
        messages_available = int(attributes.get('ApproximateNumberOfMessages', 0))
        messages_in_flight = int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
        messages_delayed = int(attributes.get('ApproximateNumberOfMessagesDelayed', 0))
        
        # Queue configuration
        visibility_timeout = int(attributes.get('VisibilityTimeout', 0))
        message_retention = int(attributes.get('MessageRetentionPeriod', 0))
        max_message_size = int(attributes.get('MaximumMessageSize', 0))
        delay_seconds = int(attributes.get('DelaySeconds', 0))
        
        # Check if FIFO queue
        is_fifo = attributes.get('FifoQueue', 'false').lower() == 'true'
        
        # Get queue ARN
        queue_arn = attributes.get('QueueArn', 'N/A')
        
        # Send test message
        test_message_body = 'health_check_test_message'
        send_response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=test_message_body,
            MessageAttributes={
                'Source': {
                    'DataType': 'String',
                    'StringValue': 'health_check'
                }
            }
        )
        
        message_id = send_response.get('MessageId')
        send_success = message_id is not None
        
        # Receive and delete test message
        receive_response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
            MessageAttributeNames=['All']
        )
        
        messages = receive_response.get('Messages', [])
        receive_success = False
        
        if messages:
            for msg in messages:
                if msg.get('Body') == test_message_body:
                    # Delete the test message
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=msg['ReceiptHandle']
                    )
                    receive_success = True
                    break
        
        return {
            'status': 'healthy',
            'service': 'sqs',
            'message': 'Successfully connected to SQS',
            'details': {
                'connection': {
                    'region': Config.AWS_REGION,
                    'queue_url': queue_url,
                    'queue_name': queue_name
                },
                'queue': {
                    'arn': queue_arn,
                    'is_fifo': is_fifo,
                    'visibility_timeout_seconds': visibility_timeout,
                    'message_retention_seconds': message_retention,
                    'max_message_size_bytes': max_message_size,
                    'delay_seconds': delay_seconds
                },
                'messages': {
                    'available': messages_available,
                    'in_flight': messages_in_flight,
                    'delayed': messages_delayed
                },
                'test_result': {
                    'send_success': send_success,
                    'message_id': message_id,
                    'receive_success': receive_success,
                    'delete_success': receive_success
                }
            }
        }
        
    except NoCredentialsError:
        return {
            'status': 'unhealthy',
            'service': 'sqs',
            'message': 'AWS credentials not found'
        }
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        return {
            'status': 'unhealthy',
            'service': 'sqs',
            'message': f'SQS error ({error_code}): {error_message}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'sqs',
            'message': f'Unexpected error: {str(e)}'
        }