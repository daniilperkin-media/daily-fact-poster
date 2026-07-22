"""
Daily Fact Poster — Unified Pipeline Entry Point
=================================================
Combines both former entry points (main.py + generate_and_post.py) into a
single pipeline controlled entirely by CLI flags.

Usage:
    python main.py [options]

Options:
    --dry-run       Generate all local files; skip live social media posts
    --no-video      Skip voiceover + TikTok video generation (faster)
    --no-tiktok     Skip TikTok posting
    --no-telegram   Skip Telegram posting
    --no-discord    Skip Discord posting
    --no-webhook    Skip Make.com webhook (Threads / Instagram / X)
    --multi-format  Also generate a native 9:16 vertical graphic card

Examples:
    python main.py --dry-run
    python main.py --no-video --multi-format
    python main.py --no-tiktok --no-discord
"""
import argparse
import datetime
import os
import subprocess
import sys

import requests
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from logger import get_logger
from history_manager import load_history, save_history, record_post, get_past_topics
from fact_generator import generate_fact
from script_generator import generate_multi_scene_script
from image_generator import generate_image
from graphic_builder import build_graphic_card
from video_builder import image_to_video
from voice_generator import generate_voiceover
from uploader import upload_image
from poster import post_to_make_webhook
from tiktok_poster import post_to_tiktok

log = get_logger()
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")


# ── Platform helpers ──────────────────────────────────────────────────────────

def post_to_telegram(image_path: str, caption: str) -> bool:
    """Post an image + caption to a Telegram channel via Bot API."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID",   "").strip()
    if not bot_token or not chat_id:
        log.info("[SKIP] Telegram — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    log.info(f"Posting to Telegram ({chat_id})…")
    try:
        with open(image_path, "rb") as photo:
            res = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": photo},
                timeout=30,
            )
        if res.status_code == 200:
            log.info("✅ Telegram posted!")
            return True
        log.warning(f"❌ Telegram failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        log.error(f"Telegram error: {e}")
    return False


def post_to_discord(image_path: str, caption: str) -> bool:
    """Post an image + caption to a Discord channel via webhook."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        log.info("[SKIP] Discord — DISCORD_WEBHOOK_URL not set.")
        return False
    log.info("Posting to Discord…")
    try:
        with open(image_path, "rb") as f:
            res = requests.post(
                webhook_url,
                data={"content": caption},
                files={"file": (os.path.basename(image_path), f, "image/png")},
                timeout=30,
            )
        if res.status_code in (200, 204):
            log.info("✅ Discord posted!")
            return True
        log.warning(f"❌ Discord failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        log.error(f"Discord error: {e}")
    return False


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    dry_run:      bool = False,
    with_video:   bool = True,
    with_tiktok:  bool = True,
    with_telegram: bool = True,
    with_discord: bool = True,
    with_webhook: bool = True,
    multi_format: bool = False,
) -> None:
    """
    Run the full content-generation and social-publishing pipeline.

    Args:
        dry_run:       If True, generate local files but skip all posting.
        with_video:    Generate neural voiceover + 9:16 TikTok MP4.
        with_tiktok:   Post video to TikTok (requires TIKTOK_* env vars).
        with_telegram: Post image card to Telegram (requires TELEGRAM_* env vars).
        with_discord:  Post image card to Discord webhook.
        with_webhook:  Trigger Make.com webhook for Threads / Instagram / X.
        multi_format:  Also build a native 9:16 vertical graphic card.
    """
    sep = "=" * 60
    log.info(sep)
    log.info("🚀  Daily Fact Poster Pipeline starting")
    log.info(f"    {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(
        f"    Mode: {'DRY RUN' if dry_run else 'PRODUCTION'} | "
        f"Video: {'on' if with_video else 'off'} | "
        f"Multi-format: {'on' if multi_format else 'off'}"
    )
    log.info(sep)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    # ── 1. History ────────────────────────────────────────────────
    log.info("\n[1/7] Loading post history…")
    history     = load_history()
    past_topics = get_past_topics(history)

    # ── 2. Generate fact / script ─────────────────────────────────
    log.info("\n[2/7] Generating fact…")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if with_video and openrouter_key and not openrouter_key.startswith("sk-or-v1-your_"):
        fact_data = generate_multi_scene_script(past_topics)
    else:
        fact_data = generate_fact(past_topics)

    log.info(f"  ► [{fact_data.get('category')}] {fact_data.get('title')}")
    log.info(f"  ► {fact_data.get('fact_short')}")

    category = fact_data.get("category", "")

    # ── 3. Generate AI background image ───────────────────────────
    log.info("\n[3/7] Generating AI background image…")
    raw_img_path = os.path.join(_OUTPUT_DIR, "raw_image.png")
    # For multi-format runs, generate a vertical image so it works for both cards
    img_gen_size = "vertical" if multi_format else "square"
    generate_image(fact_data["image_prompt"], raw_img_path, size=img_gen_size)

    # ── 4. Build graphic card(s) ──────────────────────────────────
    log.info("\n[4/7] Building graphic card(s)…")
    card_square   = os.path.join(_OUTPUT_DIR, "daily_fact_card.png")
    card_vertical = os.path.join(_OUTPUT_DIR, "daily_fact_card_vertical.png")

    build_graphic_card(
        background_path=raw_img_path,
        title=fact_data.get("title", "Did You Know?"),
        fact_text=fact_data.get("fact_short", ""),
        output_path=card_square,
        category=category,
        size="square",
    )

    if multi_format:
        build_graphic_card(
            background_path=raw_img_path,
            title=fact_data.get("title", "Did You Know?"),
            fact_text=fact_data.get("fact_short", ""),
            output_path=card_vertical,
            category=category,
            size="vertical",
        )

    # ── 5. Voiceover & video ──────────────────────────────────────
    video_path = None
    if with_video:
        log.info("\n[5/7] Generating voiceover & video…")
        audio_path = os.path.join(_OUTPUT_DIR, "narration.mp3")
        video_path = os.path.join(_OUTPUT_DIR, "daily_fact_video.mp4")

        narration = fact_data.get("narration") or fact_data.get("fact_short", "")
        generate_voiceover(narration, audio_path)

        # Use native vertical card for video if available (sharper text)
        if multi_format and os.path.exists(card_vertical):
            video_src  = card_vertical
            video_size = "vertical"
        else:
            video_src  = card_square
            video_size = "square"

        image_to_video(
            image_path=video_src,
            output_video_path=video_path,
            duration=12,
            audio_path=audio_path,
            image_size=video_size,
            ken_burns=True,
        )
    else:
        log.info("\n[5/7] Skipping video generation (--no-video).")

    # ── 6. Upload square image card ───────────────────────────────
    log.info("\n[6/7] Uploading graphic card…")
    image_url = upload_image(card_square)

    # ── 7. Copy caption to Windows clipboard ──────────────────────
    caption = fact_data.get("caption", "")
    try:
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value @'\n{caption}\n'@"],
            check=False,
            timeout=5,
        )
        log.info("Caption copied to clipboard.")
    except Exception:
        pass  # silently skip on non-Windows or if powershell unavailable

    # ── Dry-run summary ───────────────────────────────────────────
    if dry_run:
        log.info("\n" + sep)
        log.info("[DRY RUN] All local files generated — no posts sent.")
        log.info(f"  Square card:    file:///{card_square.replace(chr(92), '/')}")
        if multi_format and os.path.exists(card_vertical):
            log.info(f"  Vertical card:  file:///{card_vertical.replace(chr(92), '/')}")
        if video_path and os.path.exists(video_path):
            log.info(f"  TikTok video:   file:///{video_path.replace(chr(92), '/')}")
        log.info(f"  Image URL:      {image_url}")
        log.info(f"\nCaption:\n{'-' * 50}\n{caption}\n{'-' * 50}")
        log.info(sep)
        return

    # ── Post to platforms ─────────────────────────────────────────
    log.info("\n[7/7] Publishing to social platforms…")
    posted: list[str] = []

    if with_tiktok and video_path:
        tiktok_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
        if post_to_tiktok(video_path, caption, tiktok_token):
            posted.append("TikTok")

    if with_telegram:
        if post_to_telegram(card_square, caption):
            posted.append("Telegram")

    if with_discord:
        if post_to_discord(card_square, caption):
            posted.append("Discord")

    if with_webhook:
        if post_to_make_webhook(fact_data, image_url):
            posted.append("Make.com/Webhook")

    # ── Save history (always, even if no platform succeeded) ──────
    record_post(history, fact_data, image_url, posted)
    save_history(history)
    log.info(f"History updated. Posted to: {posted if posted else ['none']}")

    log.info("\n" + sep)
    log.info("🎉  Pipeline completed!")
    log.info(f"\n📋  CAPTION (also in clipboard):\n{'-' * 50}\n{caption}\n{'-' * 50}")
    log.info(sep)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Daily Fact Poster — AI-powered social media content pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py --dry-run                     generate & preview without posting
  python main.py --no-video                    image-only (faster, skips TTS + FFmpeg)
  python main.py --multi-format                generate 1:1 + 9:16 cards
  python main.py --no-tiktok --no-discord      post via webhook only
        """,
    )
    parser.add_argument("--dry-run",      action="store_true", help="Generate files locally; skip all live posts")
    parser.add_argument("--no-video",     action="store_true", help="Skip voiceover and TikTok video generation")
    parser.add_argument("--no-tiktok",   action="store_true", help="Skip TikTok posting")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram posting")
    parser.add_argument("--no-discord",  action="store_true", help="Skip Discord posting")
    parser.add_argument("--no-webhook",  action="store_true", help="Skip Make.com webhook")
    parser.add_argument("--multi-format", action="store_true", help="Also generate a 9:16 vertical graphic card")
    args = parser.parse_args()

    try:
        run_pipeline(
            dry_run=args.dry_run,
            with_video=not args.no_video,
            with_tiktok=not args.no_tiktok,
            with_telegram=not args.no_telegram,
            with_discord=not args.no_discord,
            with_webhook=not args.no_webhook,
            multi_format=args.multi_format,
        )
    except KeyboardInterrupt:
        log.info("\nPipeline interrupted by user.")
        sys.exit(0)
    except Exception as err:
        log.error(f"\n❌ Pipeline failed: {err}", exc_info=True)
        sys.exit(1)
