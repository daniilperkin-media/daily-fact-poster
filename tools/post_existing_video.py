"""Post an EXISTING video file to TikTok as an inbox draft (no generation).

Exercises only the posting path — token check/auto-refresh, inbox init,
upload transfer and status polling — without spending generation credits.

Usage (from anywhere, no .venv needed):
    uv run --python 3.12 --no-project --with requests --with python-dotenv \
        python tools/post_existing_video.py <video_path> [caption]
"""
import os
import sys

from dotenv import load_dotenv

# Make the package importable when this file is run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daily_fact_poster.paths import REPO_ROOT  # noqa: E402
from daily_fact_poster.tiktok_poster import post_video_to_tiktok  # noqa: E402

load_dotenv(os.path.join(REPO_ROOT, ".env"))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: post_existing_video.py <video_path> [caption]")
        return 2

    video = sys.argv[1]
    caption = sys.argv[2] if len(sys.argv) > 2 else "Pipeline test upload — safe to ignore/delete."

    ok = post_video_to_tiktok(video_path=video, title="Pipeline test", caption=caption)
    print("RESULT:", "SUCCESS (draft delivered to inbox)" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
