import boto3
from botocore.exceptions import ClientError
from config import Config


def get_s3_client():
    return boto3.client('s3', region_name=Config.AWS_REGION)


def poster_exists(filename):
    try:
        s3 = get_s3_client()
        key = f"posters/{filename}"
        
        s3.head_object(Bucket=Config.S3_BUCKET_NAME, Key=key)
        return True
        
    except ClientError:
        return False


def download_poster(filename):
    try:
        s3 = get_s3_client()
        key = f"posters/{filename}"
        
        response = s3.get_object(Bucket=Config.S3_BUCKET_NAME, Key=key)
        return response['Body'].read()
        
    except ClientError as e:
        print(f"S3 download error: {e}")
        return None


def upload_poster(filename, file_data, content_type='image/jpeg'):
    try:
        s3 = get_s3_client()
        key = f"posters/{filename}"
        
        s3.put_object(
            Bucket=Config.S3_BUCKET_NAME,
            Key=key,
            Body=file_data,
            ContentType=content_type,
            CacheControl='max-age=31536000'
        )
        
        # Generate public URL
        url = f"https://{Config.S3_BUCKET_NAME}.s3.{Config.AWS_REGION}.amazonaws.com/{key}"
        return url
        
    except ClientError as e:
        print(f"S3 upload error: {e}")
        return None