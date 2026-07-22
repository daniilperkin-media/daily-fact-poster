import os
import sys
import json
import argparse
import datetime
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 formatting on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fact_generator import generate_fact
from image_generator import generate_image
from graphic_builder import build_graphic_card
from uploader import upload_image
from poster import post_to_make_webhook

# Load .env variables from current directory or parent directory
load_dotenv()

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"past_topics": [], "posts_history": []}

def save_history(history_data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)

def run_pipeline(dry_run: bool = False):
    print("=" * 60)
    print("🚀 Starting Daily Fact Poster Pipeline")
    print(f"Time: {datetime.datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION POSTING'}")
    print("=" * 60)

    # 1. Load History
    history = load_history()
    past_topics = history.get("past_topics", [])

    # 2. Generate Fact via Gemini
    print("\n[Step 1/5] Generating Fact via Gemini 2.5 Flash...")
    fact_data = generate_fact(past_topics)
    print(f"Title: {fact_data.get('title')}")
    print(f"Fact: {fact_data.get('fact_short')}")

    # 3. Generate Artwork & Graphic Card
    raw_img_path = os.path.join(os.path.dirname(__file__), "output", "raw_image.png")
    final_card_path = os.path.join(os.path.dirname(__file__), "output", "daily_fact_card.png")

    print("\n[Step 2/5] Generating AI Background Visual...")
    generate_image(fact_data["image_prompt"], raw_img_path)

    print("\n[Step 3/5] Building Social Media Graphic Card...")
    build_graphic_card(
        background_path=raw_img_path,
        title=fact_data.get("title", "Did You Know?"),
        fact_text=fact_data.get("fact_short", ""),
        output_path=final_card_path
    )

    # 4. Upload Image
    print("\n[Step 4/5] Uploading Graphic Card to S3...")
    image_url = upload_image(final_card_path)

    # 5. Post to Make.com Webhook
    print("\n[Step 5/5] Triggering Webhook Post...")
    post_to_make_webhook(fact_data, image_url, dry_run=dry_run)

    # Update history if not dry run
    if not dry_run:
        history.setdefault("past_topics", []).append(fact_data.get("title"))
        history.setdefault("posts_history", []).append({
            "timestamp": datetime.datetime.now().isoformat(),
            "title": fact_data.get("title"),
            "fact": fact_data.get("fact_short"),
            "image_url": image_url
        })
        save_history(history)
        print("\nHistory updated successfully.")

    print("\n🎉 Pipeline Execution Completed Successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Fact Poster CLI")
    parser.add_argument("--dry-run", action="store_true", help="Run full pipeline without sending live social posts")
    args = parser.parse_args()

    try:
        run_pipeline(dry_run=args.dry_run)
    except Exception as err:
        print(f"\n❌ Pipeline failed: {err}")
        sys.exit(1)
