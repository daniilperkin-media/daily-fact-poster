"""
DEPRECATED — use `python main.py` instead.

This script is kept for backward compatibility only.
All functionality has been merged into main.py with full feature parity.

Old equivalents:
    generate_and_post.py             →  python main.py
    generate_and_post.py --dry-run   →  python main.py --dry-run
    generate_and_post.py (no video)  →  python main.py --no-video
"""
import argparse
import sys

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from logger import get_logger
from main import run_pipeline

log = get_logger()

if __name__ == "__main__":
    log.warning(
        "generate_and_post.py is deprecated. "
        "Please use 'python main.py' directly (all flags are identical)."
    )
    parser = argparse.ArgumentParser(description="[DEPRECATED] Use main.py instead.")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--no-video", action="store_true")
    args = parser.parse_args()

    try:
        run_pipeline(dry_run=args.dry_run, with_video=not args.no_video)
    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
