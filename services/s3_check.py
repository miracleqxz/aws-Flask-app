import boto3
from botocore.exceptions import ClientError
from config import Config


def check_s3():
    try:
        s3 = boto3.client('s3', region_name=Config.AWS_REGION)
        
        s3.head_bucket(Bucket=Config.S3_BUCKET_NAME)
        
        location_response = s3.get_bucket_location(Bucket=Config.S3_BUCKET_NAME)
        bucket_region = location_response['LocationConstraint'] or 'us-east-1'
        
        objects_response = s3.list_objects_v2(
            Bucket=Config.S3_BUCKET_NAME,
            MaxKeys=10
        )
        
        object_count = objects_response.get('KeyCount', 0)
        total_size = sum(obj['Size'] for obj in objects_response.get('Contents', []))
        
        test_key = 'health-check-test.txt'
        test_content = b'health check test'
        s3.put_object(
            Bucket=Config.S3_BUCKET_NAME,
            Key=test_key,
            Body=test_content
        )
        
        get_response = s3.get_object(
            Bucket=Config.S3_BUCKET_NAME,
            Key=test_key
        )
        retrieved_content = get_response['Body'].read()
        read_success = (retrieved_content == test_content)
        
        s3.delete_object(
            Bucket=Config.S3_BUCKET_NAME,
            Key=test_key
        )
        
        versioning_response = s3.get_bucket_versioning(Bucket=Config.S3_BUCKET_NAME)
        versioning_status = versioning_response.get('Status', 'Disabled')
        
        return {
            'status': 'healthy',
            'service': 's3',
            'message': 'Successfully connected to Amazon S3',
            'details': {
                'connection': {
                    'region': Config.AWS_REGION,
                    'bucket': Config.S3_BUCKET_NAME
                },
                'bucket': {
                    'name': Config.S3_BUCKET_NAME,
                    'region': bucket_region,
                    'versioning': versioning_status
                },
                'objects': {
                    'count_sample': object_count,
                    'total_size_sample': f"{total_size / 1024:.2f} KB"
                },
                'test_result': {
                    'write_success': True,
                    'read_success': read_success,
                    'delete_success': True,
                    'test_key': test_key
                }
            }
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            message = f'Bucket not found: {Config.S3_BUCKET_NAME}'
        elif error_code == '403':
            message = f'Access denied to bucket: {Config.S3_BUCKET_NAME}'
        else:
            message = f'AWS error: {e.response["Error"]["Message"]}'
        
        return {
            'status': 'unhealthy',
            'service': 's3',
            'message': message
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 's3',
            'message': f'Unexpected error: {str(e)}'
        }