"""
Fact generation using Google Gemini API.

Improvements over the original:
- Uses http_utils.post_with_retry for robust network calls
- Uses logger instead of print()
- Gemini already returns clean JSON with responseMimeType=application/json,
  so no regex stripping is needed (was brittle)
- Adds 'narration' field to the schema (kept for downstream consumers)
- Includes a virality_score self-check: re-requests once if score < 7
- Falls back to a hardcoded sample fact on any failure
"""
import json
import os
from typing import Any

from constants import PLACEHOLDER_GEMINI_KEY, is_unset_secret
from history_manager import is_duplicate, load_history
from http_utils import post_with_retry
from logger import get_logger

log = get_logger()

_FALLBACK_FACT: dict[str, Any] = {
    "category":     "Science",
    "title":        "Ancient Honey Discovery",
    "fact_short":   "Honey found inside 3,000-year-old Egyptian tombs is still 100% edible today due to its low moisture and acidic pH.",
    "narration":    (
        "Did you know honey never spoils? Archaeologists found honey in ancient Egyptian tombs "
        "over three thousand years old — and it's still perfectly edible. The secret? "
        "Honey's low moisture and natural acidity make it impossible for bacteria to survive."
    ),
    "caption":      (
        "🍯 Mind-blowing science fact of the day!\n\n"
        "Did you know honey never spoils? Archaeologists have found pots of honey in ancient "
        "Egyptian tombs that are over 3,000 years old and still perfectly edible.\n\n"
        "#DailyFact #DidYouKnow #ScienceFacts #FunFacts #MindBlown"
    ),
    "image_prompt": (
        "A glowing golden honey jar inside an ancient Egyptian pyramid tomb, "
        "3d digital render, cinematic lighting, dramatic shadows, rich amber tones, "
        "9:16 vertical composition"
    ),
    "virality_score": 8,
}

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key={api_key}"
)


def _build_prompt(past_topics_str: str) -> str:
    return f"""
You are a viral social media content creator specializing in fascinating, verified facts.
Generate 1 mind-blowing fact of the day.

Avoid topics related to: {past_topics_str}.

Respond ONLY with a single valid JSON object (no markdown, no extra text):
{{
  "category": "Space | Science | History | Nature | Technology | Human Body",
  "title": "Short punchy title (max 4-5 words)",
  "fact_short": "Core mind-blowing fact in 1-2 clear sentences (max 30 words) for a graphic card.",
  "narration": "Natural 15-20 second voiceover script (~50 words). Engaging and mind-blowing.",
  "caption": "Full social media caption with emojis and 5 highly targeted, dynamic hashtags trending in this specific niche.",
  "image_prompt": "Cinematic 3D visual prompt (no text in image, rich colors, high detail, 9:16 vertical).",
  "virality_score": 8
}}
"""


def _call_gemini(api_key: str, past_topics_str: str) -> dict[str, Any]:
    """Make one Gemini API call and return parsed JSON dict."""
    url = _GEMINI_URL.format(api_key=api_key)
    payload = {
        "contents": [{"parts": [{"text": _build_prompt(past_topics_str)}]}],
        "generationConfig": {
            "temperature": 0.8,
            "responseMimeType": "application/json",  # Gemini returns clean JSON — no regex needed
        },
    }
    response = post_with_retry(url, json=payload, timeout=30, retries=3, backoff=5)
    text_content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text_content)


def generate_fact(
    past_topics: list[str] | None = None,
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a daily interesting fact using Google Gemini 2.0 Flash.

    If the generated fact has a virality_score < 7, regenerates once with
    a higher temperature to get a more engaging result.

    Args:
        past_topics: Optional list of past topic titles to avoid duplicates.
            If provided (e.g. by the main pipeline, which already loaded
            history), it is used directly. ``None`` triggers a fresh load
            from disk so this function remains usable standalone.
        history: Optional already-loaded history dict for duplicate checks.
            If ``None``, history is loaded from disk. Callers that already
            have ``history`` should pass it through to avoid a redundant
            second disk read.

    Returns:
        Dict with keys: category, title, fact_short, narration, caption,
        image_prompt, virality_score.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if is_unset_secret(api_key, PLACEHOLDER_GEMINI_KEY):
        log.warning("GEMINI_API_KEY not set — returning fallback sample fact.")
        return _FALLBACK_FACT

    past_topics_str = ", ".join(past_topics[-150:]) if past_topics else "None"
    # Only load history from disk if the caller did not pass it in. The main
    # pipeline already loads history and passes past_topics, so this avoids
    # a redundant second read of history.json on every pipeline run.
    if history is None:
        history = load_history()

    for attempt in range(3):
        try:
            data = _call_gemini(api_key, past_topics_str)

            title = data.get('title', '')
            fact_short = data.get('fact_short', '')
            score = data.get("virality_score", 10)

            if is_duplicate(history, title, fact_short):
                log.warning(f"Generated duplicate fact '{title}' — regenerating (attempt {attempt+1}/3)…")
                continue

            if score < 7:
                log.info(f"Virality score {score}/10 is low — regenerating for better content (attempt {attempt+1}/3)…")
                continue

            log.info(
                f"Fact generated ✓ [{data.get('category')}] "
                f'"{title}" (virality: {score})'
            )
            return data
        except Exception as e:
            log.warning(f"Gemini API failed on attempt {attempt+1} ({e})")

    log.warning("All Gemini attempts failed or resulted in low score/duplicates — using fallback fact.")
    return _FALLBACK_FACT


if __name__ == "__main__":
    fact = generate_fact()
    print(json.dumps(fact, indent=2, ensure_ascii=False))
