import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config


def check_s3():
    try:
        s3 = boto3.client(
            's3',
            region_name=Config.AWS_REGION
        )

        bucket_name = Config.S3_BUCKET_NAME

        s3.head_bucket(Bucket=bucket_name)

        location = s3.get_bucket_location(Bucket=bucket_name)
        bucket_region = location.get('LocationConstraint') or 'us-east-1'

        objects_response = s3.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=10
        )

        object_count = objects_response.get('KeyCount', 0)
        is_truncated = objects_response.get('IsTruncated', False)


        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        versioning_status = versioning.get('Status', 'Disabled')

        test_key = '_health_check_test_object'
        test_content = b'health check test'

        # Write test
        s3.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content
        )

        # Read test
        read_response = s3.get_object(
            Bucket=bucket_name,
            Key=test_key
        )
        read_content = read_response['Body'].read()
        read_success = read_content == test_content

        # Delete test
        s3.delete_object(
            Bucket=bucket_name,
            Key=test_key
        )

        return {
            'status': 'healthy',
            'service': 's3',
            'message': 'Successfully connected to S3',
            'details': {
                'connection': {
                    'region': Config.AWS_REGION,
                    'bucket': bucket_name
                },
                'bucket': {
                    'region': bucket_region,
                    'versioning': versioning_status,
                    'sample_object_count': object_count,
                    'has_more_objects': is_truncated
                },
                'permissions': {
                    'read': True,
                    'write': True,
                    'delete': True,
                    'read_content_match': read_success
                }
            }
        }

    except NoCredentialsError:
        return {
            'status': 'unhealthy',
            'service': 's3',
            'message': 'AWS credentials not found'
        }
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        return {
            'status': 'unhealthy',
            'service': 's3',
            'message': f'S3 error ({error_code}): {error_message}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 's3',
            'message': f'Unexpected error: {str(e)}'
        }
