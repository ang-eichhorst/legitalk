import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone
import mimetypes
from dotenv import load_dotenv
import json
import time
import argparse

# --- Color Codes for Console Output ---
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def get_s3_objects(bucket, prefix=''):
    """Get a dictionary of objects in the S3 bucket and their last modified times."""
    s3_objects = {}
    try:
        s3 = boto3.client("s3")
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    s3_objects[obj['Key']] = obj['LastModified']
    except ClientError as e:
        print(f"{RED}Error listing bucket objects: {e}{RESET}")
    return s3_objects

def find_distribution_id_for_bucket(bucket_name):
    """Find the CloudFront distribution ID associated with an S3 bucket."""
    try:
        cloudfront = boto3.client("cloudfront")
        distributions = cloudfront.list_distributions()
        for dist in distributions.get('DistributionList', {}).get('Items', []):
            for origin in dist.get('Origins', {}).get('Items', []):
                if bucket_name in origin.get('DomainName', ''):
                    return dist['Id']
    except ClientError as e:
        print(f"Error finding distribution: {e}")
    return None

def invalidate_cloudfront_cache(distribution_id, items):
    """Create a CloudFront invalidation for the specified items."""
    if not distribution_id:
        print("Could not find a distribution ID to invalidate.")
        return
    if not items:
        print("No files to invalidate.")
        return
        
    print(f"Creating invalidation for {len(items)} files in distribution: {distribution_id}")
    try:
        cloudfront = boto3.client("cloudfront")
        cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(items),
                    'Items': [f'/{item}' for item in items] # Paths must start with a '/'
                },
                'CallerReference': f'invalidation-{time.time()}'
            }
        )
        print("Invalidation created successfully.")
    except ClientError as e:
        print(f"Error creating invalidation: {e}")

def sync_meetings_to_s3(source_dir: str, bucketname: str = None, prefix: str = 'meetings'):
    """
    Synchronizes the local meetings directory with the S3 bucket and generates a JSON index
    based on the final state of the S3 bucket.
    """
    # --- Load Configuration ---
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    BUCKET_NAME = bucketname
    if not BUCKET_NAME:
        env_path = os.path.join(project_root, '.env')
        load_dotenv(dotenv_path=env_path)
        BUCKET_NAME = os.getenv("BUCKET_NAME")
    
    if not BUCKET_NAME:
        print(f"{RED}Error: BUCKET_NAME must be set in the .env file or passed as an argument.{RESET}")
        return

    local_meetings_dir = os.path.abspath(source_dir)
    
    print(f"--- Starting Sync of '{local_meetings_dir}' to S3 bucket '{BUCKET_NAME}' ---")

    if not os.path.isdir(local_meetings_dir):
        print(f"{RED}Error: Local meetings directory not found at '{local_meetings_dir}'{RESET}")
        return

    s3 = boto3.client("s3")
    s3_objects_before_sync = get_s3_objects(BUCKET_NAME, prefix=f'{prefix}/')
    uploaded_files = []

    # --- 1. Sync individual files from local to S3 ---
    for root, dirs, files in os.walk(local_meetings_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, local_meetings_dir)
            s3_key = os.path.join(prefix, relative_path).replace('\\', '/')
            local_last_modified = datetime.fromtimestamp(os.path.getmtime(local_path)).astimezone(timezone.utc)

            if s3_key in s3_objects_before_sync and local_last_modified <= s3_objects_before_sync[s3_key]:
                print(f"{YELLOW}SKIP (up-to-date): {s3_key}{RESET}")
            else:
                action = "UPLOAD (newer)" if s3_key in s3_objects_before_sync else "UPLOAD (new)"
                print(f"{GREEN}{action}: {s3_key}{RESET}")
                upload_file(s3, local_path, BUCKET_NAME, s3_key)
                uploaded_files.append(s3_key)

    # --- 2. (Removed) JSON Index Generation ---
    # The application now uses S3 XML discovery, so meetings_index.json is no longer required.


    # --- 3. Invalidate CloudFront Cache ---
    if uploaded_files:
        dist_id = find_distribution_id_for_bucket(BUCKET_NAME)
        invalidate_cloudfront_cache(dist_id, uploaded_files)

    print("\n--- Sync Complete ---")

def upload_file(s3_client, local_path, bucket, s3_key):
    """Helper function to upload a single file with the correct MIME type."""
    content_type, _ = mimetypes.guess_type(local_path)
    if content_type is None:
        content_type = 'application/octet-stream'
    
    try:
        s3_client.upload_file(
            local_path,
            bucket,
            s3_key,
            ExtraArgs={'ContentType': content_type}
        )
    except ClientError as e:
        print(f"{RED}Error uploading '{s3_key}': {e}{RESET}")

def main():
    """Parses command-line arguments and calls the main sync function."""
    parser = argparse.ArgumentParser(description="Synchronizes a local meetings directory with an S3 bucket.")
    parser.add_argument(
        '--source-dir',
        default='localhost/meetings',
        help='Path to the local meetings directory to sync from. Defaults to "localhost/meetings".'
    )
    parser.add_argument(
        '--bucketname',
        default=None,
        help='The name of the s3 bucket to sync to. If not provided, the value is read from the .env file.'
    )
    parser.add_argument(
        '--prefix',
        default='meetings',
        help='S3 key prefix to sync under. Defaults to "meetings". Use "other" for other/ content.'
    )
    args = parser.parse_args()
    sync_meetings_to_s3(source_dir=args.source_dir, bucketname=args.bucketname, prefix=args.prefix)

if __name__ == '__main__':
    main()