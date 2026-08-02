"""
History management for Daily Fact Poster.

Persists past_topics (used to avoid duplicate content) and posts_history
(used for analytics). Caps the past_topics list at MAX_TOPICS entries so
history.json never grows unboundedly.

Usage:
    from history_manager import load_history, save_history, record_post, get_past_topics

    history    = load_history()
    past_topics = get_past_topics(history)
    # … run pipeline …
    record_post(history, fact_data, image_url, platforms=["TikTok", "Telegram"])
    save_history(history)
"""
import datetime
import json
import os
from typing import Any

MAX_TOPICS = 2000
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")


def load_history() -> dict[str, Any]:
    """Load history from disk. Returns a fresh structure if file does not exist."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # Back-fill stats key for old files that don't have it
        data.setdefault("stats", {"total_posts": 0, "last_run": None, "platform_counts": {}})
        return data
    return {
        "past_topics": [],
        "posts_history": [],
        "stats": {"total_posts": 0, "last_run": None, "platform_counts": {}},
    }


def save_history(data: dict[str, Any]) -> None:
    """
    Persist history to disk.
    Silently trims past_topics to the most recent MAX_TOPICS entries
    to prevent unbounded file growth.
    """
    if len(data.get("past_topics", [])) > MAX_TOPICS:
        data["past_topics"] = data["past_topics"][-MAX_TOPICS:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
        image_url:  The public URL of the uploaded graphic card.
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
