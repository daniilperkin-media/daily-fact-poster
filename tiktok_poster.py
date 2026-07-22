"""
TikTok Content Posting API integration.

Improvements over the original:
- Polls publish_id status after upload (was fire-and-forget)
  → confirms PUBLISH_COMPLETE or surfaces FAILED status
- Uses logger instead of print()
- Clears unused variable warning in status polling
"""
import os
import time

import requests

from logger import get_logger

log = get_logger()

_POLL_INTERVAL = 5    # seconds between status checks
_POLL_TIMEOUT  = 120  # maximum seconds to wait for processing


def get_client_credentials_token(client_key: str, client_secret: str) -> str | None:
    """Fetch a TikTok Access Token via the Client Credentials OAuth flow."""
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    try:
        res = requests.post(
            url,
            data={
                "client_key":    client_key,
                "client_secret": client_secret,
                "grant_type":    "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if res.status_code == 200:
            token = res.json().get("access_token")
            log.info("Retrieved TikTok access token via Client Credentials.")
            return token
        log.warning(f"TikTok token fetch failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        log.warning(f"TikTok token fetch error: {e}")
    return None


def _poll_publish_status(publish_id: str, token: str) -> str:
    """
    Poll TikTok's publish status endpoint until a terminal state is reached
    or the timeout is exceeded.

    Returns:
        Final status string: "PUBLISH_COMPLETE", "FAILED", "CANCELLED", or "TIMEOUT".
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    deadline = time.time() + _POLL_TIMEOUT
    elapsed  = 0
    status   = "UNKNOWN"

    while time.time() < deadline:
        try:
            res = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
                timeout=20,
            )
            if res.status_code == 200:
                status = res.json().get("data", {}).get("status", "UNKNOWN")
                log.info(f"TikTok publish status [{elapsed}s elapsed]: {status}")
                if status in ("PUBLISH_COMPLETE", "FAILED", "CANCELLED"):
                    return status
            else:
                log.warning(f"Status poll returned HTTP {res.status_code}: {res.text[:200]}")
        except Exception as e:
            log.warning(f"Status poll error: {e}")

        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    log.warning(
        f"TikTok status polling timed out after {_POLL_TIMEOUT}s "
        f"(last known status: '{status}')."
    )
    return "TIMEOUT"


def post_to_tiktok(
    video_path: str,
    caption: str = "",
    access_token: str = None,
) -> bool:
    """
    Post a video file to TikTok using the official Content Posting API.
    Polls publish_id after upload to confirm processing.

    Args:
        video_path:    Local path to the MP4 file.
        caption:       Optional caption text (currently for reference only;
                       TikTok inbox drafts don't support pre-filled captions).
        access_token:  Overrides TIKTOK_ACCESS_TOKEN env var.

    Returns:
        True if upload succeeded and status is PUBLISH_COMPLETE (or TIMEOUT).
        False if upload failed or credentials are missing.
    """
    token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()

    # Try Client Credentials fallback
    if not token:
        client_key    = os.environ.get("TIKTOK_CLIENT_KEY",    "").strip()
        client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
        if client_key and client_secret:
            token = get_client_credentials_token(client_key, client_secret)

    if not token:
        local_path = os.path.abspath(video_path).replace("\\", "/")
        log.warning(
            "[SKIP] No TikTok credentials found (TIKTOK_ACCESS_TOKEN or "
            f"TIKTOK_CLIENT_KEY/SECRET). Video available locally: file:///{local_path}"
        )
        return False

    if not os.path.exists(video_path):
        log.error(f"TikTok video file not found: {video_path}")
        return False

    file_size = os.path.getsize(video_path)
    headers   = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── 1. Initiate upload session ─────────────────────────────────
    log.info("Initializing TikTok upload session…")
    init_res = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
        headers=headers,
        json={
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        file_size,
                "total_chunk_count": 1,
            }
        },
        timeout=30,
    )

    if init_res.status_code != 200:
        log.error(f"TikTok init failed ({init_res.status_code}): {init_res.text}")
        return False

    res_data   = init_res.json().get("data", {})
    upload_url = res_data.get("upload_url")
    publish_id = res_data.get("publish_id")

    if not upload_url:
        log.error(f"No upload_url in TikTok init response: {init_res.json()}")
        return False

    # ── 2. Upload video binary ─────────────────────────────────────
    log.info(f"Uploading video to TikTok ({file_size / 1_048_576:.1f} MB)…")
    with open(video_path, "rb") as vf:
        put_res = requests.put(
            upload_url,
            data=vf,
            headers={
                "Content-Type":   "video/mp4",
                "Content-Length": str(file_size),
                "Content-Range":  f"bytes 0-{file_size - 1}/{file_size}",
            },
            timeout=180,
        )

    if put_res.status_code not in (200, 201):
        log.error(f"TikTok binary upload failed ({put_res.status_code}): {put_res.text}")
        return False

    log.info(f"Video uploaded (publish_id={publish_id}). Polling processing status…")

    # ── 3. Poll publish status ─────────────────────────────────────
    final_status = _poll_publish_status(publish_id, token)

    if final_status == "PUBLISH_COMPLETE":
        log.info("✅ TikTok video published successfully!")
        return True
    elif final_status == "TIMEOUT":
        # Upload succeeded; TikTok processing continues asynchronously
        log.warning("⏳ TikTok still processing — check your TikTok app inbox for the draft.")
        return True
    else:
        log.error(f"❌ TikTok publish ended with status: {final_status}")
        return False
