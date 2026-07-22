"""
Make.com webhook poster.
Sends fact data + image URL to Make.com for distribution to Threads, Instagram, Telegram, X.

Fix over original:
- No longer raises ValueError when MAKE_WEBHOOK_URL is missing.
  Instead logs a [SKIP] warning and returns False, consistent with other posting modules.
"""
import json
import os

import requests

from logger import get_logger

log = get_logger()


def post_to_make_webhook(
    data: dict,
    image_url: str,
    dry_run: bool = False,
) -> bool:
    """
    Trigger the Make.com webhook with fact content and a public image URL.

    Make.com distributes the post to Threads, Telegram, Instagram, and X.

    Args:
        data:      Fact dict (title, fact_short, category, caption).
        image_url: Public HTTPS URL of the graphic card image.
        dry_run:   If True, log the payload but do not send the request.

    Returns:
        True if the webhook was triggered (or skipped in dry-run).
        False if the URL is not configured or the request fails.
    """
    webhook_url = os.environ.get("MAKE_WEBHOOK_URL", "").strip()

    payload = {
        "title":      data.get("title"),
        "fact":       data.get("fact_short"),
        "category":   data.get("category"),
        "caption":    data.get("caption"),
        "image_url":  image_url,
        "source":     "Daily_Fact_Poster",
    }

    log.info("--- Make.com Webhook Payload ---")
    log.info(json.dumps(payload, indent=2, ensure_ascii=False))

    if dry_run:
        log.info("[DRY RUN] Webhook request skipped.")
        return True

    if not webhook_url:
        log.warning(
            "[SKIP] MAKE_WEBHOOK_URL not set in .env — skipping Make.com webhook post. "
            "Add it to .env to enable Threads / Instagram / X posting."
        )
        return False

    log.info("Posting to Make.com Webhook…")
    try:
        response = requests.post(webhook_url, json=payload, timeout=20)
        response.raise_for_status()
        log.info("✅ Make.com Webhook triggered successfully!")
        return True
    except requests.RequestException as e:
        log.error(f"❌ Make.com Webhook failed: {e}")
        return False
