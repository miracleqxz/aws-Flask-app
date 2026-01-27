#!/usr/bin/env python3
import os

import boto3
from botocore.exceptions import ClientError


def sync_posters_from_local():
    bucket_name = os.getenv("S3_BUCKET_NAME")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not bucket_name:
        raise SystemExit("S3_BUCKET_NAME is not set")

    s3 = boto3.client("s3", region_name=region)

    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        raise SystemExit(f"Bucket '{bucket_name}' is not accessible: {e}")

    existing_keys = set()
    continuation_token = None

    while True:
        kwargs = {"Bucket": bucket_name}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**kwargs)

        for obj in response.get("Contents", []):
            existing_keys.add(obj["Key"])

        if not response.get("IsTruncated"):
            break

        continuation_token = response.get("NextContinuationToken")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    posters_dir = os.path.join(os.path.dirname(base_dir), "posters")

    if not os.path.isdir(posters_dir):
        raise SystemExit(f"Posters directory not found: {posters_dir}")

    uploaded = 0
    for filename in os.listdir(posters_dir):
        if not filename.lower().endswith(".jpg"):
            continue

        if filename in existing_keys:
            continue

        path = os.path.join(posters_dir, filename)
        with open(path, "rb") as f:
            s3.put_object(
                Bucket=bucket_name,
                Key=filename,
                Body=f.read(),
                ContentType="image/jpeg",
            )
        uploaded += 1

    print(f"Uploaded {uploaded} new posters to s3://{bucket_name}")


if __name__ == "__main__":
    sync_posters_from_local()

