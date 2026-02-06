import boto3
import os
from config import Config


def upload_posters_to_s3(folder_path='posters'):
    print("Uploading Posters to S3")

    if not os.path.exists(folder_path):
        print(f"\nFolder not found: {folder_path}")
        print("Please create the folder and add poster images.")
        return

    s3 = boto3.client('s3', region_name=Config.AWS_REGION)
    bucket_name = Config.S3_BUCKET_NAME

    # Check if bucket exists
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"S3 Bucket exists: {bucket_name}\n")
    except Exception:
        print(f"Bucket not found: {bucket_name}")
        print("Create bucket first!")
        return

    # Get list of poster files
    poster_files = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.jpeg', '.png'))]

    if not poster_files:
        print(f"No image files found in {folder_path}/")
        return

    print(f"Found {len(poster_files)} poster files\n")

    success_count = 0
    fail_count = 0

    for i, filename in enumerate(poster_files, 1):
        file_path = os.path.join(folder_path, filename)

        try:
            # Get file size
            file_size_kb = os.path.getsize(file_path) / 1024

            # Upload to S3
            s3.upload_file(
                file_path,
                bucket_name,
                filename,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )

            print(f"  {i}. {filename} ({file_size_kb:.1f} KB)")
            success_count += 1

        except Exception as e:
            print(f"  {i}. {filename} - Error: {e}")
            fail_count += 1

    print("\n" + "=" * 50)
    print(f"Uploaded: {success_count}")
    print(f"Failed: {fail_count}")
    print("=" * 50)


if __name__ == '__main__':
    upload_posters_to_s3()
