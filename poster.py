import os
import json
import requests
from typing import Dict, Any

def post_to_make_webhook(data: Dict[str, Any], image_url: str, dry_run: bool = False) -> bool:
    """
    Sends the generated fact content + image_url to the Make.com Free Webhook endpoint.
    Make.com then distributes the post to Threads, Telegram, Instagram, and X for free.
    """
    webhook_url = os.environ.get("MAKE_WEBHOOK_URL")

    payload = {
        "title": data.get("title"),
        "fact": data.get("fact_short"),
        "category": data.get("category"),
        "caption": data.get("caption"),
        "image_url": image_url,
        "source": "Daily_Fact_Poster"
    }

    print("\n--- Social Media Post Payload ---")
    print(json.dumps(payload, indent=2))

    if dry_run:
        print("\n[DRY RUN] Webhook request skipped. Payload logged above.")
        return True

    if not webhook_url:
        raise ValueError("MAKE_WEBHOOK_URL environment variable is missing.")

    print(f"\nPosting to Make.com Webhook ({webhook_url})...")
    response = requests.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()

    print("Successfully triggered Make.com Webhook!")
    return True
