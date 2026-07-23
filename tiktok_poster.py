"""
TikTok Content Posting API integration.

Uses the Direct Post endpoint (/v2/post/publish/video/init/) which supports
a configurable privacy_level. Defaults to SELF_ONLY so unaudited apps can post
immediately — change TIKTOK_PRIVACY_LEVEL in .env to PUBLIC_TO_EVERYONE once
your TikTok Developer App is approved for production access.

Workflow:
  1. Query creator info to confirm posting eligibility
  2. Init direct-post upload session with privacy + caption
  3. PUT video binary to the returned upload_url
  4. Poll publish_id until PUBLISH_COMPLETE or timeout
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
    """
    Poll TikTok's publish status endpoint until a terminal state or timeout.

    Returns:
        "PUBLISH_COMPLETE", "FAILED", "CANCELLED", or "TIMEOUT".
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
                log.info(f"TikTok publish status [{elapsed}s]: {status}")
                if status in ("PUBLISH_COMPLETE", "FAILED", "CANCELLED"):
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


def post_to_tiktok(
    video_path: str,
    caption: str = "",
    access_token: str = None,
    privacy_level: str = None,
) -> bool:
    """
    Post a video to TikTok using the Direct Post API.

    Privacy is controlled by the TIKTOK_PRIVACY_LEVEL env var (default: SELF_ONLY).
    With an unaudited TikTok Developer App, only SELF_ONLY is permitted.
    Once your app is approved, set TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE.

    After posting with SELF_ONLY:
      1. Open TikTok app  →  Me  →  find the new private video
      2. Tap ··· (More)  →  Privacy settings  →  change to Public

    Args:
        video_path:    Local path to the MP4 file.
        caption:       Post caption / title (max 2 200 chars).
        access_token:  Overrides TIKTOK_ACCESS_TOKEN env var.
        privacy_level: Overrides TIKTOK_PRIVACY_LEVEL env var.

    Returns:
        True on PUBLISH_COMPLETE or TIMEOUT (upload succeeded, still processing).
        False on failure or missing credentials.
    """
    # ── Resolve token ──────────────────────────────────────────────
    token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()

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

    # ── Resolve privacy level ──────────────────────────────────────
    privacy = (
        privacy_level
        or os.environ.get("TIKTOK_PRIVACY_LEVEL", _DEFAULT_PRIVACY).strip()
    )
    log.info(f"TikTok privacy level: {privacy}")
    if privacy == "SELF_ONLY":
        log.info(
            "  ℹ After posting: TikTok app → Me → video → ··· → Privacy → change to Public"
        )

    file_size = os.path.getsize(video_path)
    headers   = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── 1. Init direct-post upload session ────────────────────────
    log.info("Initializing TikTok direct-post upload session…")
    init_res = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title":                    caption[:2200] if caption else "Daily Fact",
                "privacy_level":            privacy,
                "disable_duet":             False,
                "disable_comment":          False,
                "disable_stitch":           False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        file_size,
                "total_chunk_count": 1,
            },
        },
        timeout=30,
    )

    if init_res.status_code != 200:
        err = init_res.json().get("error", {})
        code = err.get("code", "")
        msg  = err.get("message", init_res.text[:300])

        if code == "unaudited_client_can_only_post_to_private_accounts":
            log.error(
                "TikTok rejected the post because your Developer App is not yet approved "
                "for public posting. Set TIKTOK_PRIVACY_LEVEL=SELF_ONLY in .env and retry."
            )
        elif code == "spam_risk_too_many_pending_share":
            log.error(
                "TikTok rejected the post — too many pending shares.\n"
                "  Fix: open TikTok app → Me → find draft videos → ··· → Delete\n"
                "  (Dismissing inbox notifications is NOT enough — the draft must be deleted.)"
            )
        else:
            log.error(f"TikTok init failed ({init_res.status_code}): {msg}")
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
        log.info(
            f"✅ TikTok video posted successfully! (privacy: {privacy})\n"
            + (
                "   To make it public: TikTok app → Me → video → ··· → Privacy settings"
                if privacy == "SELF_ONLY" else ""
            )
        )
        return True
    elif final_status == "TIMEOUT":
        log.warning(
            "⏳ TikTok still processing — check your TikTok profile for the new private video."
        )
        return True
    else:
        log.error(f"❌ TikTok publish ended with status: {final_status}")
        return False
