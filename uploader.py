import os
import datetime
import requests
import boto3
from botocore.exceptions import ClientError

def upload_to_free_host(file_path: str) -> str:
    """
    Uploads a file to tmpfiles.org (100% free, no registration, no credit card required).
    Returns a direct public HTTPS URL.
    """
    url = "https://tmpfiles.org/api/v1/upload"
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(url, files=files, timeout=30)
        response.raise_for_status()
        res_data = response.json()
        page_url = res_data.get("data", {}).get("url", "")
        # Convert to direct link for social media platforms
        direct_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        print(f"Uploaded image to Free Host: {direct_url}")
        return direct_url

def upload_image(file_path: str) -> str:
    """
    Uploads image to AWS S3 if credentials exist. 
    Otherwise, automatically falls back to Free Host (No credit card needed).
    """
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("AWS_S3_BUCKET")
    region = os.environ.get("AWS_REGION", "us-east-1")

    # If AWS is not configured or placeholder keys are used, use Free Host
    if not access_key or not secret_key or access_key.startswith("your_") or "AQ." in access_key:
        print("[INFO] AWS S3 keys not set. Using 100% free image hosting (No credit card needed)...")
        return upload_to_free_host(file_path)

    date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    s3_key = f"daily_facts/{date_str}_{os.path.basename(file_path)}"

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )

    try:
        s3_client.upload_file(
            file_path,
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": "image/png"}
        )
        url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
        print(f"Uploaded image to S3: {url}")
        return url
    except Exception as e:
        print(f"[WARNING] S3 Upload failed ({e}). Falling back to free image host...")
        return upload_to_free_host(file_path)
