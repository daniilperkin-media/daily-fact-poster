"""
TikTok Content Posting API integration.

Uploads the generated carousel video to the creator's TikTok Drafts (the
documented inbox upload flow) and falls back to a Direct Post init when the
inbox path is unavailable. Expired access tokens are refreshed automatically
when a refresh token is configured (see tiktok_auth.py).

Success states:
- SEND_TO_USER_INBOX   — draft delivered; the user finishes it in the TikTok app.
- PUBLISH_COMPLETE     — TikTok fully published the post.
"""
import os
import time

import requests

from constants import PLACEHOLDER_TIKTOK_ACCESS_TOKEN, is_unset_secret
from logger import get_logger
from tiktok_auth import refresh_access_token

log = get_logger()

_POLL_INTERVAL = 5    # seconds between status checks
_POLL_TIMEOUT  = 120  # max seconds to wait for processing

# Valid values: PUBLIC_TO_EVERYONE | MUTUAL_FOLLOW_FRIENDS |
#               FOLLOWER_OF_CREATOR | SELF_ONLY
_DEFAULT_PRIVACY = "SELF_ONLY"

# TikTok rejects captions longer than 2200 UTF-16 runes.
_MAX_CAPTION = 2200

_INBOX_INIT_URL   = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
_DIRECT_INIT_URL  = "https://open.tiktokapis.com/v2/post/publish/video/init/"
_STATUS_URL       = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"

_SUCCESS_STATUSES = ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _error_info(res: requests.Response) -> tuple[str, str]:
    """Best-effort extraction of (error.code, error.message) from a response."""
    try:
        err = res.json().get("error", {})
    except ValueError:
        err = {}
    return err.get("code", ""), err.get("message", res.text[:300])


def _token_invalid(res: requests.Response) -> bool:
    code, _ = _error_info(res)
    return res.status_code == 401 or code == "access_token_invalid"


def _init_with_refresh(endpoint: str, token: str, payload: dict) -> tuple[requests.Response, str]:
    """POST an init request; if the token is expired, refresh once and retry."""
    res = requests.post(endpoint, headers=_headers(token), json=payload, timeout=30)
    if _token_invalid(res):
        refreshed = refresh_access_token()
        if refreshed:
            token = refreshed
            res = requests.post(endpoint, headers=_headers(token), json=payload, timeout=30)
    return res, token


def _resolve_privacy(token: str, configured: str) -> str:
    """
    Best-effort check of `configured` against the creator info API.

    TikTok requires privacy_level to be one of the account's allowed options,
    otherwise the direct-post init fails with privacy_level_option_mismatch.
    """
    try:
        res = requests.post(_CREATOR_INFO_URL, headers=_headers(token), timeout=15)
    except requests.RequestException as e:
        log.warning(f"creator_info query failed ({e}) — using configured privacy level.")
        return configured
    if res.status_code != 200:
        log.warning(
            f"creator_info query returned HTTP {res.status_code} — using configured privacy level."
        )
        return configured
    options = res.json().get("data", {}).get("privacy_level_options", [])
    if configured in options:
        return configured
    if "SELF_ONLY" in options:
        log.warning(
            f"privacy_level '{configured}' is not among the account's options "
            f"{options} — using SELF_ONLY."
        )
        return "SELF_ONLY"
    return configured


def _poll_publish_status(publish_id: str, token: str) -> str:
    """Poll the publish status until it reaches a terminal state or times out."""
    deadline = time.time() + _POLL_TIMEOUT
    elapsed  = 0
    status   = "UNKNOWN"

    while time.time() < deadline:
        try:
            res = requests.post(
                _STATUS_URL,
                headers=_headers(token),
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
    access_token: str | None = None,
    privacy_level: str | None = None,
) -> bool:
    """
    Upload a video to TikTok.

    Returns True once the video is on TikTok — either delivered to the
    creator's Drafts (SEND_TO_USER_INBOX) or fully published (PUBLISH_COMPLETE).
    """
    token = (access_token or os.environ.get("TIKTOK_ACCESS_TOKEN", "")).strip()
    if is_unset_secret(token, PLACEHOLDER_TIKTOK_ACCESS_TOKEN):
        log.warning(
            "[SKIP] No usable TikTok user access token (.env.example placeholder "
            "or empty). Run tiktok_auth.py to authorize — client-credentials "
            "tokens cannot upload or publish videos."
        )
        return False

    if not os.path.exists(video_path):
        log.error(f"Video file not found: {video_path}")
        return False

    video_size = os.path.getsize(video_path)
    privacy = (
        privacy_level
        or os.environ.get("TIKTOK_PRIVACY_LEVEL", _DEFAULT_PRIVACY).strip()
        or _DEFAULT_PRIVACY
    )
    source_info = {
        "source": "FILE_UPLOAD",
        "video_size": video_size,
        "chunk_size": video_size,
        "total_chunk_count": 1,
    }

    # ── 1. Initialize the upload ───────────────────────────────────
    # Inbox (Drafts) first: it is the documented upload flow, needs only the
    # video.upload scope, and avoids the unaudited-client publish restrictions.
    log.info(f"Uploading {video_size} bytes to TikTok (inbox/Drafts)…")
    init_res, token = _init_with_refresh(_INBOX_INIT_URL, token, {"source_info": source_info})
    used = "inbox/Drafts"

    if init_res.status_code != 200:
        code, msg = _error_info(init_res)
        log.warning(f"TikTok inbox init failed ({init_res.status_code}) [{code}]: {msg}")

        # Fallback: Direct Post init (publishes immediately when the app is
        # allowed to; unaudited clients stay private-viewing only).
        log.info("Trying Direct Post init as fallback…")
        privacy = _resolve_privacy(token, privacy)
        direct_payload = {
            "post_info": {
                "title": title[:90],
                "description": caption[:_MAX_CAPTION],
                "privacy_level": privacy,
                "disable_comment": False,
            },
            "source_info": source_info,
        }
        init_res, token = _init_with_refresh(_DIRECT_INIT_URL, token, direct_payload)
        used = "direct post"
        if init_res.status_code != 200:
            code, msg = _error_info(init_res)
            log.error(f"TikTok Direct Post init failed ({init_res.status_code}) [{code}]: {msg}")
            return False

    try:
        data = init_res.json().get("data", {})
    except ValueError:
        data = {}
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")

    if not publish_id or not upload_url:
        log.error(f"Missing publish_id or upload_url in TikTok init response: {init_res.text[:300]}")
        return False

    log.info(f"Upload initiated via {used} (publish_id={publish_id}). Transferring file…")

    # ── 2. Transfer the file data ──────────────────────────────────
    try:
        with open(video_path, "rb") as f:
            video_data = f.read()

        put_headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(video_size),
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        }
        upload_res = requests.put(upload_url, data=video_data, headers=put_headers, timeout=120)

        if upload_res.status_code not in (200, 201):
            log.error(f"TikTok upload transfer failed ({upload_res.status_code}): {upload_res.text[:300]}")
            return False
    except Exception as e:
        log.error(f"Failed to upload video data: {e}")
        return False

    log.info(f"Transfer complete (publish_id={publish_id}). Polling processing status…")

    # ── 3. Poll the publish status ─────────────────────────────────
    final_status = _poll_publish_status(publish_id, token)

    if final_status in _SUCCESS_STATUSES:
        if final_status == "SEND_TO_USER_INBOX":
            log.info(
                "✅ Video delivered to your TikTok inbox/Drafts — open the TikTok app "
                "to finish the post (the caption is already on your clipboard)."
            )
        else:
            log.info("✅ TikTok video published.")
        return True

    if final_status == "TIMEOUT":
        # A timed-out poll is NOT a confirmed delivery: recording success
        # here would write "posted" into history while nothing was confirmed.
        log.error("⏳ TikTok publish poll timed out without confirmation — treating as failure.")
        return False

    log.error(f"❌ TikTok publish ended with status: {final_status}")
    return False
