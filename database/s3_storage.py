import boto3
import redis
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config

logger = logging.getLogger(__name__)


def get_s3_client():
    return boto3.client('s3', region_name=Config.AWS_REGION)


def get_redis_client():
    return redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        socket_connect_timeout=5,
        socket_timeout=5,
        decode_responses=False
    )


def download_poster(filename):
    cache_key = f"poster:{filename}"

    try:
        redis_client = get_redis_client()
        cached = redis_client.get(cache_key)

        if cached:
            logger.info(f"Cache HIT: {filename}")
            return cached
    except Exception as e:
        logger.error(f"Redis cache error: {e}")

    try:
        logger.info(f"Cache MISS: {filename} - downloading from S3")

        s3 = get_s3_client()
        response = s3.get_object(Bucket=Config.S3_BUCKET_NAME, Key=filename)
        data = response['Body'].read()

        try:
            redis_client = get_redis_client()
            redis_client.setex(cache_key, 3600, data)
            logger.info(f"Cached {filename} in Redis")
        except Exception as e:
            logger.error(f"Redis set error: {e}")

        return data

    except NoCredentialsError as e:
        logger.error(f"AWS credentials error: {e}")
        return None
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"S3 ClientError ({error_code}): {e}")
        return None
    except Exception as e:
        logger.error(f"S3 download error: {e}")
        return None


def poster_exists(filename):
    try:
        s3 = get_s3_client()
        s3.head_object(Bucket=Config.S3_BUCKET_NAME, Key=filename)
        return True
    except Exception:
        return False


def upload_poster(filename, file_data, content_type='image/jpeg'):
    try:
        s3 = get_s3_client()

        s3.put_object(
            Bucket=Config.S3_BUCKET_NAME,
            Key=filename,
            Body=file_data,
            ContentType=content_type,
            CacheControl='max-age=31536000'
        )

        url = f"https://{Config.S3_BUCKET_NAME}.s3.{Config.AWS_REGION}.amazonaws.com/{filename}"
        return url

    except Exception as e:
        logger.error(f"S3 upload error: {e}")
        return None
