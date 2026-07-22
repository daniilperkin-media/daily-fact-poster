import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 formatting on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from fact_generator import generate_fact
from image_generator import generate_image
from graphic_builder import build_graphic_card
from video_builder import image_to_video
from tiktok_poster import post_to_tiktok

def post_to_telegram(image_path: str, caption: str, bot_token: str, chat_id: str) -> bool:
    """Posts local image + caption directly to a Telegram channel."""
    if not bot_token or not chat_id:
        print("[SKIP] Telegram bot token or chat ID not set.")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    print(f"Posting to Telegram channel ({chat_id})...")
    with open(image_path, "rb") as photo:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": photo},
            timeout=30
        )
    if response.status_code == 200:
        print("✅ Telegram post successful!")
        return True
    else:
        print(f"❌ Telegram post failed: {response.text}")
        return False

def post_to_discord(image_path: str, caption: str, webhook_url: str) -> bool:
    """Posts local image + caption directly to a Discord channel webhook."""
    if not webhook_url:
        print("[SKIP] Discord webhook URL not set.")
        return False

    print("Posting to Discord webhook...")
    with open(image_path, "rb") as f:
        response = requests.post(
            webhook_url,
            data={"content": caption},
            files={"file": (os.path.basename(image_path), f, "image/png")},
            timeout=30
        )
    if response.status_code in [200, 204]:
        print("✅ Discord post successful!")
        return True
    else:
        print(f"❌ Discord post failed: {response.text}")
        return False

def run_local_command(dry_run: bool = False):
    print("=" * 60)
    print("🎯 LOCAL FACT GENERATOR & INSTANT POSTER")
    print("=" * 60)

    # 1. Generate Fact & Caption via Gemini
    print("\n1️⃣ Generating Fact & Caption via AI...")
    fact_data = generate_fact()
    print(f"\n📌 Title: {fact_data.get('title')}")
    print(f"📝 Fact: {fact_data.get('fact_short')}\n")

    # 2. Render Image & Graphic Card
    raw_path = os.path.join(os.path.dirname(__file__), "output", "raw_image.png")
    card_path = os.path.join(os.path.dirname(__file__), "output", "daily_fact_card.png")
    video_path = os.path.join(os.path.dirname(__file__), "output", "daily_fact_video.mp4")

    print("2️⃣ Generating AI Background Image...")
    generate_image(fact_data["image_prompt"], raw_path)

    print("3️⃣ Building Graphic Card...")
    build_graphic_card(
        background_path=raw_path,
        title=fact_data.get("title", "Did You Know?"),
        fact_text=fact_data.get("fact_short", ""),
        output_path=card_path
    )

    print("4️⃣ Creating 9:16 Vertical Video for TikTok...")
    image_to_video(card_path, video_path, duration=5)

    caption = fact_data.get("caption", "")

    if dry_run:
        print("\n[DRY RUN COMPLETE] Local files created:")
        print(f"  Image Card: file:///{card_path.replace('\\', '/')}")
        print(f"  TikTok Video (9:16 MP4): file:///{video_path.replace('\\', '/')}")
        print("\nCaption created:")
        print(caption)
        return

    # 3. Direct Local Posting
    print("\n5️⃣ Posting Directly to TikTok & Connected Channels...")

    # TikTok
    tiktok_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    post_to_tiktok(video_path, caption, tiktok_token)

    # Telegram
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    post_to_telegram(card_path, caption, tg_token, tg_chat)

    # Discord
    discord_url = os.environ.get("DISCORD_WEBHOOK_URL")
    post_to_discord(card_path, caption, discord_url)

    print("\n🎉 ALL DONE! Photo + Caption generated & posted directly!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Generate photo & caption locally without posting")
    args = parser.parse_args()
    run_local_command(dry_run=args.dry_run)
