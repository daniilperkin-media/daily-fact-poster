import os
import json
import requests

def post_to_tiktok(video_path: str, caption: str = "", access_token: str = None) -> bool:
    """
    Posts a video file to TikTok using TikTok's official Content Posting API.
    Ref: https://open.tiktokapis.com/v2/post/publish/inbox/video/init/
    """
    token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not token:
        print("[SKIP] TIKTOK_ACCESS_TOKEN is missing in .env.")
        print(f"       Video generated locally at: file:///{os.path.abspath(video_path).replace('\\', '/')}")
        return False

    if not os.path.exists(video_path):
        print(f"[ERROR] TikTok video file missing: {video_path}")
        return False

    file_size = os.path.getsize(video_path)

    # 1. Initiate Video Upload (TikTok Official Endpoint)
    init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1
        }
    }

    print("Initializing TikTok Content Posting API session...")
    res = requests.post(init_url, headers=headers, json=payload, timeout=30)
    
    if res.status_code != 200:
        print(f"❌ TikTok init failed ({res.status_code}): {res.text}")
        return False

    res_json = res.json()
    upload_url = res_json.get("data", {}).get("upload_url")
    publish_id = res_json.get("data", {}).get("publish_id")

    if not upload_url:
        print(f"❌ TikTok error: No upload_url returned ({res_json})")
        return False

    # 2. Upload Video File Binary to upload_url (PUT request)
    print("Uploading video binary to TikTok servers...")
    with open(video_path, "rb") as video_file:
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"
        }
        put_res = requests.put(upload_url, data=video_file, headers=upload_headers, timeout=120)

    if put_res.status_code in [200, 201]:
        print(f"✅ Video successfully uploaded to TikTok inbox! (Publish ID: {publish_id})")
        print("   Check your TikTok mobile app inbox notifications to review and publish!")
        return True
    else:
        print(f"❌ TikTok binary upload failed ({put_res.status_code}): {put_res.text}")
        return False
