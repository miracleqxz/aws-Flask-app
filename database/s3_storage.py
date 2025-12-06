import boto3
from botocore.exceptions import ClientError
from config import Config


def get_s3_client():
    return boto3.client('s3', region_name=Config.AWS_REGION)


def poster_exists(filename):
    try:
        s3 = get_s3_client()
        
        s3.head_object(Bucket=Config.S3_BUCKET_NAME, Key=filename)  
        return True
        
    except ClientError:
        return False


def download_poster(filename):
    try:
        s3 = get_s3_client()
        
        response = s3.get_object(Bucket=Config.S3_BUCKET_NAME, Key=filename)  
        return response['Body'].read()
        
    except ClientError as e:
        print(f"S3 download error: {e}")
        return None


def upload_poster(filename, file_data, content_type='image/jpeg'):
    try:
        s3 = get_s3_client()
        
        s3.put_object(
            Bucket=Config.S3_BUCKET_NAME,
            Key=filename,  # ← БЕЗ posters/
            Body=file_data,
            ContentType=content_type,
            CacheControl='max-age=31536000'
        )
        
        url = f"https://{Config.S3_BUCKET_NAME}.s3.{Config.AWS_REGION}.amazonaws.com/{filename}"
        return url
        
    except ClientError as e:
        print(f"S3 upload error: {e}")
        return None