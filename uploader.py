"""
Image upload: AWS S3 (preferred) with automatic fallback to tmpfiles.org.

Fixes over the original:
- Removed fragile "AQ." in access_key heuristic (caused valid S3 keys to be skipped)
- Replaced with a clean length/placeholder check
- Added clear warning that tmpfiles.org URLs expire after ~1 hour
- Uses logger instead of print()
"""
import datetime
import os

import boto3
import requests
from botocore.exceptions import ClientError

from logger import get_logger

log = get_logger()


def upload_to_free_host(file_path: str) -> str:
    """
    Upload a file to tmpfiles.org (free, no registration required).

    ⚠ URLs expire after approximately 1 hour.
    Suitable for dry-run testing; use S3 for production.

    Returns:
        Direct public HTTPS download URL.
    """
    log.warning(
        "Using tmpfiles.org fallback — URLs expire in ~1 hour. "
        "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_S3_BUCKET for production."
    )
    url = "https://tmpfiles.org/api/v1/upload"
    with open(file_path, "rb") as f:
        response = requests.post(url, files={"file": f}, timeout=30)
    response.raise_for_status()
    page_url = response.json().get("data", {}).get("url", "")
    direct_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    log.info(f"Uploaded to free host: {direct_url}")
    return direct_url


def upload_image(file_path: str) -> str:
    """
    Upload an image to AWS S3 if credentials are properly configured,
    otherwise fall back to tmpfiles.org.

    Required S3 env vars:
        AWS_ACCESS_KEY_ID
        AWS_SECRET_ACCESS_KEY
        AWS_S3_BUCKET
        AWS_REGION (optional, default: us-east-1)

    Returns:
        Public HTTPS URL to the uploaded image.
    """
    access_key  = os.environ.get("AWS_ACCESS_KEY_ID",  "").strip()
    secret_key  = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    bucket_name = os.environ.get("AWS_S3_BUCKET", "").strip()
    region      = os.environ.get("AWS_REGION", "us-east-1")

    # Validate: all three fields must be present and not placeholder values
    s3_ready = (
        len(access_key) >= 16
        and len(secret_key) >= 16
        and bucket_name
        and not access_key.startswith("your_")
        and not secret_key.startswith("your_")
    )

    if not s3_ready:
        log.info("AWS S3 not configured — switching to free image host.")
        return upload_to_free_host(file_path)

    date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    s3_key = f"daily_facts/{date_str}_{os.path.basename(file_path)}"

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    try:
        s3_client.upload_file(
            file_path,
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": "image/png"},
        )
        url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
        log.info(f"Uploaded to S3: {url}")
        return url
    except ClientError as e:
        log.warning(f"S3 upload failed ({e}) — falling back to free host.")
        return upload_to_free_host(file_path)
