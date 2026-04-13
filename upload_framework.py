import boto3
import os
import json
import mimetypes
import time
import hashlib
import argparse
import shutil
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# --- Color Codes for Console Output ---
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'
CYAN = '\033[96m'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Load Environment Variables ---
load_dotenv()
BUCKET_NAME = os.getenv("BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def get_s3_objects(bucket):
    """Get a dictionary of objects in the S3 bucket and their ETags."""
    s3_objects = {}
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket):
            if 'Contents' in page:
                for obj in page['Contents']:
                    s3_objects[obj['Key']] = obj['ETag'].strip('"')
    except ClientError as e:
        print(f"Error listing bucket objects: {e}")
    return s3_objects

def calculate_local_md5(file_path):
    """Calculate the MD5 hash of a local file."""
    with open(file_path, 'rb') as f:
        md5 = hashlib.md5()
        while chunk := f.read(8192):
            md5.update(chunk)
    return md5.hexdigest()

def find_distribution_id_for_bucket(bucket_name):
    """Find the CloudFront distribution ID associated with an S3 bucket."""
    try:
        cloudfront = boto3.client("cloudfront")
        distributions = cloudfront.list_distributions()
        items = distributions.get('DistributionList', {}).get('Items', [])
        print(f"DEBUG: Checking {len(items)} distributions for bucket '{bucket_name}'")
        for dist in items:
            # Check Origins
            for origin in dist.get('Origins', {}).get('Items', []):
                if bucket_name in origin.get('DomainName', ''):
                    print(f"DEBUG: Found match in origin domain: {origin.get('DomainName', '')}")
                    return dist['Id']
            # Check Aliases (CNAMEs)
            aliases = dist.get('Aliases', {}).get('Items', [])
            if bucket_name in aliases:
                print(f"DEBUG: Found match in aliases: {aliases}")
                return dist['Id']
            # print(f"DEBUG: Checked {dist['Id']}, aliases: {aliases}")
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

def sync_to_s3(source_dir, bucket_name, files_to_sync, args):
    """Syncs files from source_dir to an S3 bucket."""
    print(f"Syncing to S3 Bucket: {bucket_name}")
    
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3_objects = get_s3_objects(bucket_name)
    uploaded_files = []

    for file_key in files_to_sync:
        local_path = os.path.join(source_dir, file_key)
        
        if not os.path.exists(local_path):
            print(f"{YELLOW}Warning: File '{local_path}' not found, skipping.{RESET}")
            continue

        local_md5 = calculate_local_md5(local_path)
        remote_etag = s3_objects.get(file_key)

        if local_md5 == remote_etag:
            print(f"{CYAN}Skipping '{file_key}' (unchanged).{RESET}")
            continue

        content_type, _ = mimetypes.guess_type(local_path)
        if content_type is None:
            content_type = 'application/octet-stream'
            
        try:
            # We use global 'args' earlier but passed it here now.
            if hasattr(args, 'dry_run') and args.dry_run:
                print(f"[Dry Run] would upload '{file_key}' (changed).")
            else:
                s3.upload_file(
                    local_path,
                    bucket_name,
                    file_key,
                    ExtraArgs={'ContentType': content_type}
                )
                print(f"{GREEN}Uploading '{file_key}' (changed)...{RESET}")
                uploaded_files.append(file_key)
        except ClientError as e:
             print(f"{RED}Failed to upload '{file_key}': {e}{RESET}")


    
    # --- 6. Generate and Upload config.json ---
    print(f"\n{CYAN}Generating config.json for bucket: {bucket_name}{RESET}")
    config_data = {
        "bucketName": bucket_name,
        "region": AWS_REGION
    }
    config_json_path = os.path.join(source_dir, "config.json")
    try:
        with open(config_json_path, "w") as f:
            json.dump(config_data, f, indent=4)
        
        # Upload it
        s3_key = "config.json"
        
        if hasattr(args, 'dry_run') and args.dry_run:
             print(f"[Dry Run] would upload {s3_key}")
        else:
             content_type = 'application/json'
             s3.upload_file(
                 config_json_path,
                 bucket_name,
                 s3_key,
                 ExtraArgs={'ContentType': content_type}
             )
             print(f"{GREEN}Uploaded config.json{RESET}")
             uploaded_files.append(s3_key)

    except Exception as e:
        print(f"{RED}Error generating/uploading config.json: {e}{RESET}")
    finally:
        if os.path.exists(config_json_path):
            try:
                os.remove(config_json_path)
            except:
                pass

    # --- 7. Invalidate CloudFront ---
    if uploaded_files:
        if hasattr(args, 'dry_run') and args.dry_run:
             print("[Dry Run] Skipping invalidation.")
        else:
             dist_id = find_distribution_id_for_bucket(bucket_name)
             invalidate_cloudfront_cache(dist_id, uploaded_files)
    else:
        print("No files were uploaded, skipping invalidation.")




def sync_to_directory(source_dir, target_dir, files_to_sync, args):
    """Syncs files from source_dir to a local target directory."""
    print(f"Syncing to Local Directory: {target_dir}")
    
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
            print(f"Created target directory: {target_dir}")
        except OSError as e:
            print(f"Error creating target directory: {e}")
            return

    copied_count = 0
    for file_key in files_to_sync:
        local_path = os.path.join(source_dir, file_key)
        target_path = os.path.join(target_dir, file_key)
        
        if not os.path.exists(local_path):
            print(f"{YELLOW}Warning: File '{local_path}' not found, skipping.{RESET}")
            continue

        # Check if target exists and compare content (using MD5 for consistency)
        should_copy = True
        if os.path.exists(target_path):
            local_md5 = calculate_local_md5(local_path)
            target_md5 = calculate_local_md5(target_path)
            if local_md5 == target_md5:
                should_copy = False
                print(f"{CYAN}Skipping '{file_key}' (unchanged).{RESET}")

        if should_copy:
            try:
                # Ensure subdirectories exist in target
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(local_path, target_path)
                print(f"{GREEN}Copying '{file_key}' to '{target_path}'...{RESET}")
                copied_count += 1
            except OSError as e:
                print(f"Error copying '{file_key}': {e}")

    print(f"--- Local Sync Complete. Copied {copied_count} files. ---")

def main():
    """
    Uploads website framework files to a target (S3 bucket or local directory).
    """
    parser = argparse.ArgumentParser(description="Syncs website framework files to S3 or a local directory.")
    parser.add_argument(
        '--target',
        required=True,
        help='Target destination. Can be an S3 bucket name or a local directory path.'
    )
    parser.add_argument(
        '--manifest-path',
        help='Path to the manifest file listing files to sync. Defaults to sync_manifest.txt in the source directory.'
    )
    parser.add_argument(
        '--source-dir',
        default=os.path.join(SCRIPT_DIR, "localhost"),
        help='Path to the source directory containing the files. Defaults to localhost in the script directory.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform a dry run without uploading or modifying files.'
    )
    args = parser.parse_args()

    print("--- Starting Framework Sync ---")
    
    source_dir = os.path.abspath(args.source_dir)
    
    # Determine manifest path
    if args.manifest_path:
        manifest_path = os.path.abspath(args.manifest_path)
    else:
        manifest_path = os.path.join(source_dir, "sync_manifest.txt")
        # Fallback to script dir if not found in source (for backward compatibility or mixed setups)
        if not os.path.exists(manifest_path):
             fallback_path = os.path.join(SCRIPT_DIR, "sync_manifest.txt")
             if os.path.exists(fallback_path):
                 manifest_path = fallback_path

    try:
        with open(manifest_path, 'r') as f:
            files_to_sync = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"{YELLOW}Error: Manifest file not found at {manifest_path}{RESET}")
        return

    print(f"Found {len(files_to_sync)} files to sync from manifest: {manifest_path}")
    print(f"Using source directory: {source_dir}")

    # Add all pagefind/ files (auto-generated binary index — too many to list in manifest)
    pagefind_dir = os.path.join(source_dir, "pagefind")
    if os.path.isdir(pagefind_dir):
        for root, _, filenames in os.walk(pagefind_dir):
            for fname in filenames:
                full_path = os.path.join(root, fname)
                rel_key = os.path.relpath(full_path, source_dir).replace(os.sep, "/")
                if rel_key not in files_to_sync:
                    files_to_sync.append(rel_key)
        print(f"Added pagefind/ directory ({len([f for f in files_to_sync if f.startswith('pagefind/')])} files).")
    else:
        print("Note: pagefind/ directory not found — run build_search_index.sh before deploying.")
    
    # Determine target type
    target = args.target
    if os.path.isdir(target) or os.path.exists(target): 
        # If it exists and is a dir, or doesn't exist but looks like a path (we'll assume dir creation is intended if it looks like a path? 
        # Actually, user said "if it is not already... assumed... source directory". 
        # Let's stick to the plan: if os.path.isdir(target) -> directory. Else -> S3.
        # But what if they want to create a NEW directory? 
        # Let's check if it *looks* like a path (contains separators) or if it exists as a dir.
        if os.path.isdir(target) or "\\" in target or "/" in target:
             sync_to_directory(source_dir, os.path.abspath(target), files_to_sync)
        else:
             sync_to_s3(source_dir, target, files_to_sync)
    else:
        # If it doesn't exist, and has no separators, assume S3 bucket.
        # If it has separators, assume it's a new directory path.
        if "\\" in target or "/" in target:
             sync_to_directory(source_dir, os.path.abspath(target), files_to_sync, args)
        else:
             sync_to_s3(source_dir, target, files_to_sync, args)

if __name__ == "__main__":
    main()