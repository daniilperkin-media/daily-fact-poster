"""
TikTok Content Posting API integration for Video uploads (FILE_UPLOAD).

Uses the Direct Post endpoint (/v2/post/publish/inbox/video/init/)
configured for Drafts.
"""
import os
import time

import requests

from logger import get_logger

log = get_logger()

_POLL_INTERVAL = 5    # seconds between status checks
_POLL_TIMEOUT  = 120  # max seconds to wait for processing

# Valid values: PUBLIC_TO_EVERYONE | MUTUAL_FOLLOW_FRIENDS | SELF_ONLY
_DEFAULT_PRIVACY = "SELF_ONLY"


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
                log.info(f"TikTok publish status [{elapsed}s]: {status}")
                if status in ("PUBLISH_COMPLETE", "FAILED", "CANCELLED", "SEND_TO_USER_INBOX"):
                    return status
            else:
                log.warning(f"Status poll HTTP {res.status_code}: {res.text[:200]}")
        except Exception as e:
            log.warning(f"Status poll error: {e}")

        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    log.warning(
        f"TikTok status polling timed out after {_POLL_TIMEOUT}s "
        f"(last known status: '{status}')."
    )
    return "TIMEOUT"


def post_video_to_tiktok(
    video_path: str,
    title: str = "Daily Fact",
    caption: str = "",
    access_token: str = None,
    privacy_level: str = None,
) -> bool:
    """
    Post a video to TikTok Drafts using FILE_UPLOAD.
    """
    token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()

    if not token:
        client_key    = os.environ.get("TIKTOK_CLIENT_KEY",    "").strip()
        client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
        if client_key and client_secret:
            token = get_client_credentials_token(client_key, client_secret)

    if not token:
        log.warning("[SKIP] No TikTok credentials found. Video available locally.")
        return False

    if not os.path.exists(video_path):
        log.error(f"Video file not found: {video_path}")
        return False

    video_size = os.path.getsize(video_path)
    privacy = privacy_level or os.environ.get("TIKTOK_PRIVACY_LEVEL", _DEFAULT_PRIVACY).strip()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── 1. Init direct-post upload session ────────────────────────
    log.info(f"Initializing TikTok video upload ({video_size} bytes)…")

    payload = {
        "post_info": {
            "title": title[:90],
            "description": caption[:4000],
            "privacy_level": privacy,
            "disable_comment": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1
        },
        "post_mode": "MEDIA_UPLOAD" # Try Drafts first (preserves caption)
    }

    init_res = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if init_res.status_code != 200:
        err = init_res.json().get("error", {})
        code = err.get("code", "")
        msg  = err.get("message", init_res.text[:300])
        log.warning(f"TikTok Direct Post init failed ({init_res.status_code}) [{code}]: {msg}")

        # Fallback to Inbox
        log.info("Trying Inbox video/init fallback...")
        payload.pop("post_mode", None)
        init_res = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if init_res.status_code != 200:
            err = init_res.json().get("error", {})
            msg = err.get("message", init_res.text[:300])
            log.error(f"Fallback TikTok init failed: {msg}")
            return False

    res_data   = init_res.json().get("data", {})
    publish_id = res_data.get("publish_id")
    upload_url = res_data.get("upload_url")

    if not publish_id or not upload_url:
        log.error(f"Missing publish_id or upload_url in TikTok init response: {init_res.json()}")
        return False

    log.info(f"Upload initiated. Transferring {video_size} bytes to TikTok…")

    # ── 2. Transfer file data ─────────────────────────────────────
    try:
        with open(video_path, "rb") as f:
            video_data = f.read()

        put_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size-1}/{video_size}"
        }
        upload_res = requests.put(upload_url, data=video_data, headers=put_headers, timeout=120)

        if upload_res.status_code not in (200, 201):
            log.error(f"TikTok upload transfer failed ({upload_res.status_code}): {upload_res.text[:300]}")
            return False

    except Exception as e:
        log.error(f"Failed to upload video data: {e}")
        return False

    log.info(f"Transfer complete (publish_id={publish_id}). Polling processing status…")

    # ── 3. Poll publish status ─────────────────────────────────────
    final_status = _poll_publish_status(publish_id, token)

    if final_status == "PUBLISH_COMPLETE":
        log.info("✅ TikTok Video posted successfully to Drafts! Open TikTok -> Me -> Drafts to add music.")
        return True
    elif final_status == "TIMEOUT":
        log.warning("⏳ TikTok still processing — check your TikTok profile later.")
        return True
    else:
        log.error(f"❌ TikTok publish ended with status: {final_status}")
        return False
