"""
Daily Fact Poster — Unified Pipeline Entry Point (TikTok Video Carousel)
=================================================
Combines script generation, AI image generation (Flux 2 Pro), compositing,
video compilation (FFmpeg), and posting into a single pipeline.

Usage:
    python main.py [options]

Options:
    --dry-run       Generate all local files; skip live social media posts
    --no-tiktok     Skip TikTok posting

Examples:
    python main.py --dry-run
    python main.py --no-tiktok
"""
import argparse
import datetime
import glob
import os
import subprocess
import sys

from dotenv import load_dotenv

# Ensure UTF-8 output on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from constants import PLACEHOLDER_OPENROUTER_KEY, is_unset_secret
from fact_generator import generate_fact
from graphic_builder import build_graphic_card
from history_manager import get_past_topics, load_history, record_post, save_history
from image_generator import generate_image
from logger import get_logger
from script_generator import generate_multi_scene_script
from tiktok_poster import post_video_to_tiktok

log = get_logger()
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    dry_run:      bool = False,
    with_tiktok:  bool = True,
) -> None:
    """
    Run the full content-generation and social-publishing pipeline.
    """
    sep = "=" * 60
    log.info(sep)
    log.info("🚀  Daily Fact Poster Pipeline (Video Carousel Mode) starting")
    log.info(f"    {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"    Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    log.info(sep)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    # ── 1. History ────────────────────────────────────────────────
    log.info("\n[1/6] Loading post history…")
    history     = load_history()
    past_topics = get_past_topics(history)

    # ── 2. Generate fact / script ─────────────────────────────────
    log.info("\n[2/6] Generating carousel script…")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not is_unset_secret(openrouter_key, PLACEHOLDER_OPENROUTER_KEY):
        fact_data = generate_multi_scene_script(past_topics, history=history)
    else:
        log.warning("OpenRouter API key missing. Carousel requires OpenRouter GPT-4o-mini.")
        # Fallback to single fact
        fact_data = generate_fact(past_topics, history=history)
        fact_data["slides"] = [
            {"text": fact_data.get("title", "Did You Know?"), "image_prompt": fact_data.get("image_prompt", "")},
            {"text": fact_data.get("fact_short", ""), "image_prompt": fact_data.get("image_prompt", "")}
        ]

    log.info(f"  ► [{fact_data.get('category')}] {fact_data.get('title')}")
    caption = fact_data.get("caption", "")

    slides = fact_data.get("slides", [])
    total_slides = len(slides)

    if total_slides == 0:
        log.error("No slides generated. Aborting.")
        return

    # ── 3. Generate Images & Build Cards ─────────────────────────
    log.info(f"\n[3/6] Generating {total_slides} AI background images and compositing cards…")

    # Remove stale slide cards from previous runs *before* writing the new
    # batch. FFmpeg's ``card_slide_%d.jpg`` pattern reads card_slide_1.jpg,
    # card_slide_2.jpg, … until the first missing file, so leftover cards
    # from a longer previous run would silently leak into the new video.
    for stale in glob.glob(os.path.join(_OUTPUT_DIR, "card_slide_*.jpg")):
        try:
            os.remove(stale)
        except OSError:
            pass
    # Raw background images are regenerated every run too; clear them so the
    # output dir never accumulates orphaned files from older runs.
    for stale in glob.glob(os.path.join(_OUTPUT_DIR, "raw_slide_*.jpg")):
        try:
            os.remove(stale)
        except OSError:
            pass

    card_paths: list[str] = []

    for i, slide in enumerate(slides):
        idx = i + 1
        log.info(f"--- Slide {idx}/{total_slides} ---")

        raw_img_path = os.path.join(_OUTPUT_DIR, f"raw_slide_{idx}.jpg")
        card_img_path = os.path.join(_OUTPUT_DIR, f"card_slide_{idx}.jpg")

        generate_image(slide["image_prompt"], raw_img_path, size="vertical")

        build_graphic_card(
            background_path=raw_img_path,
            slide_text=slide["text"],
            output_path=card_img_path,
            category=fact_data.get("category", ""),
            size="vertical",
            slide_index=idx,
            total_slides=total_slides
        )
        card_paths.append(card_img_path)

    # ── 4. Compile Video via FFmpeg ──────────────────────────────
    video_path = os.path.join(_OUTPUT_DIR, "carousel_video.mp4")
    log.info(f"\n[4/6] Compiling {total_slides} slides into Video ({video_path})…")

    # 2.5 seconds per slide = 1/2.5 framerate (0.4 fps)
    # Using libx264 for high compatibility
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", "1/2.5",
        "-i", os.path.join(_OUTPUT_DIR, "card_slide_%d.jpg"),
        "-c:v", "libx264",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        video_path
    ]

    try:
        # Capture stderr (do not send to DEVNULL) so FFmpeg failures surface
        # a real diagnostic instead of a generic "failed" message.
        subprocess.run(
            ffmpeg_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        log.info("Video compiled successfully.")
    except subprocess.CalledProcessError as e:
        log.error(f"FFmpeg failed to compile video (exit {e.returncode}):")
        if e.stderr:
            log.error(e.stderr[-2000:])
        return
    except Exception as e:
        log.error(f"FFmpeg failed to compile video: {e}")
        return

    # ── 5. Copy caption to Windows clipboard ──────────────────────
    try:
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value @'\n{caption}\n'@"],
            check=False,
            timeout=5,
        )
        log.info("\n[5/6] Caption copied to clipboard.")
    except Exception:
        pass

    # ── Dry-run summary ───────────────────────────────────────────
    if dry_run:
        log.info("\n" + sep)
        log.info("[DRY RUN] All local files generated — no posts sent.")
        log.info(f"  Video path: file:///{video_path.replace(chr(92), '/')}")
        log.info(f"\nCaption:\n{'-' * 50}\n{caption}\n{'-' * 50}")
        log.info(sep)
        return

    # ── 6. Post to platforms ─────────────────────────────────────────
    log.info("\n[6/6] Publishing to TikTok…")
    posted: list[str] = []

    if with_tiktok and os.path.exists(video_path):
        tiktok_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
        if post_video_to_tiktok(
            video_path=video_path,
            title=fact_data.get("title", "Daily Fact"),
            caption=caption,
            access_token=tiktok_token
        ):
            posted.append("TikTok")

    # ── Save history (always, even if no platform succeeded) ──────
    record_post(history, fact_data, video_path, posted)
    save_history(history)
    log.info(f"History updated. Posted to: {posted if posted else ['none']}")

    log.info("\n" + sep)
    log.info("🎉  Pipeline completed!")
    log.info(f"\n📋  CAPTION (also in clipboard):\n{'-' * 50}\n{caption}\n{'-' * 50}")
    log.info(sep)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Daily Fact Poster — AI Video Carousel Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run",      action="store_true", help="Generate files locally; skip all live posts")
    parser.add_argument("--no-tiktok",   action="store_true", help="Skip TikTok posting")
    args = parser.parse_args()

    try:
        run_pipeline(
            dry_run=args.dry_run,
            with_tiktok=not args.no_tiktok,
        )
    except KeyboardInterrupt:
        log.info("\nPipeline interrupted by user.")
        sys.exit(0)
    except Exception as err:
        log.error(f"\n❌ Pipeline failed: {err}", exc_info=True)
        sys.exit(1)
