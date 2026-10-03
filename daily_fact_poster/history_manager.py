"""
History management for Daily Fact Poster.

Persists past_topics (used to avoid duplicate content) and posts_history
(used for analytics). Caps the past_topics list at MAX_TOPICS entries so
history.json never grows unboundedly.

Usage:
    from .history_manager import load_history, save_history, record_post, get_past_topics

    history    = load_history()
    past_topics = get_past_topics(history)
    # … run pipeline …
    record_post(history, fact_data, video_path, platforms=["TikTok"])
    save_history(history)
"""
import datetime
import json
import logging
import os
import tempfile
from typing import Any

from .paths import REPO_ROOT

MAX_TOPICS = 2000
HISTORY_FILE = os.path.join(REPO_ROOT, "history.json")

logger = logging.getLogger(__name__)


def _fresh_history() -> dict[str, Any]:
    """Return a new, empty history structure."""
    return {
        "past_topics": [],
        "posts_history": [],
        "stats": {"total_posts": 0, "last_run": None, "platform_counts": {}},
    }


def load_history() -> dict[str, Any]:
    """Load history from disk. Returns a fresh structure if file does not exist.

    A corrupt history.json (e.g. a truncated write from a crash before the
    atomic swap took effect) is quarantined aside rather than allowed to crash
    the run — the file is the single source of dedup + stats truth, and losing
    it silently would re-post already-posted facts the next run.
    """
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            quarantine_path = _quarantine_corrupt_history(exc)
            logger.warning(
                "history.json corrupt (%s); quarantined to %s and starting fresh",
                exc,
                quarantine_path,
            )
            return _fresh_history()
        if not isinstance(data, dict):
            quarantine_path = _quarantine_corrupt_history(
                ValueError("history.json root is not a JSON object")
            )
            logger.warning(
                "history.json malformed (root not an object); quarantined to %s and starting fresh",
                quarantine_path,
            )
            return _fresh_history()
        # Back-fill stats key for old files that don't have it
        data.setdefault("stats", {"total_posts": 0, "last_run": None, "platform_counts": {}})
        return data
    return _fresh_history()


def _quarantine_corrupt_history(exc: BaseException) -> str:
    """Move a corrupt history file aside so it is not silently re-read.

    A timestamped name keeps successive quarantine events from clobbering a
    prior copy, giving a recovery trail instead of data loss. If the move fails
    for any reason, the original file is left in place (the caller already has
    a fresh in-memory structure, so the run proceeds regardless).
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    quarantine_path = f"{HISTORY_FILE}.corrupt-{ts}"
    try:
        os.replace(HISTORY_FILE, quarantine_path)
        return quarantine_path
    except OSError as move_exc:
        logger.error(
            "failed to quarantine corrupt history.json (%s)", move_exc
        )
        return HISTORY_FILE


def save_history(data: dict[str, Any]) -> None:
    """
    Persist history to disk.
    Silently trims past_topics to the most recent MAX_TOPICS entries
    to prevent unbounded file growth.
    """
    if len(data.get("past_topics", [])) > MAX_TOPICS:
        data["past_topics"] = data["past_topics"][-MAX_TOPICS:]
    # Atomic write: a plain overwrite truncated by a crash would corrupt the
    # one file every future run depends on for dedup and stats. Write to a
    # temp file next to the target, then atomically swap it into place.
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(HISTORY_FILE), prefix=".history", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, HISTORY_FILE)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_past_topics(history: dict[str, Any]) -> list[str]:
    """Return the list of past topic titles (for de-duplication prompting)."""
    return history.get("past_topics", [])


def is_duplicate(history: dict[str, Any], title: str, fact_short: str) -> bool:
    """
    Check if a newly generated fact is a duplicate by comparing keywords
    against past_topics. Returns True if a high similarity is found.
    """
    past_topics = get_past_topics(history)
    if not past_topics:
        return False

    def _get_keywords(text: str) -> set[str]:
        # Simple lowercase tokenization, ignoring short common words
        words = text.lower().replace(",", "").replace(".", "").split()
        return {w for w in words if len(w) > 4}

    new_keywords = _get_keywords(title + " " + fact_short)
    if not new_keywords:
        return False

    for old_topic in past_topics[-200:]:  # Check against recent 200 to save time
        old_keywords = _get_keywords(old_topic)
        if not old_keywords:
            continue
        # If there's a strong overlap in significant words (e.g. 2 or more shared long words)
        overlap = new_keywords.intersection(old_keywords)
        if len(overlap) >= 2:
            return True

    return False


def record_post(
    history: dict[str, Any],
    fact_data: dict[str, Any],
    image_url: str,
    platforms: list[str],
) -> None:
    """
    Append a new post entry to past_topics and posts_history, and update stats.

    Args:
        history:    The dict returned by load_history().
        fact_data:  The fact dict from generate_fact / generate_multi_scene_script.
        image_url:  Local path (or URL) of the video the run produced, kept for reference.
        platforms:  List of platform names where posting succeeded, e.g. ["TikTok"].
    """
    topic = fact_data.get("title", "")
    now = datetime.datetime.now().isoformat()

    history.setdefault("past_topics", []).append(topic)
    history.setdefault("posts_history", []).append(
        {
            "timestamp": now,
            "title": topic,
            "category": fact_data.get("category", ""),
            "fact": fact_data.get("fact_short", ""),
            "image_url": image_url,
            "platforms": platforms,
        }
    )

    stats = history.setdefault("stats", {"total_posts": 0, "last_run": None, "platform_counts": {}})
    stats["total_posts"] = stats.get("total_posts", 0) + 1
    stats["last_run"] = now
    counts = stats.setdefault("platform_counts", {})
    for p in platforms:
        counts[p] = counts.get(p, 0) + 1
