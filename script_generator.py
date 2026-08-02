"""
Multi-scene TikTok video script generator using OpenRouter (default model:
openai/gpt-4o-mini). Falls back to Gemini fact_generator if OpenRouter is
not configured.

Uses logger instead of print().
"""
import json
import os
import re
from typing import Any

from constants import PLACEHOLDER_OPENROUTER_KEY, is_unset_secret
from fact_generator import generate_fact as fallback_gemini_fact
from history_manager import is_duplicate, load_history
from logger import get_logger
from openrouter_client import call_openrouter_llm

log = get_logger()


def generate_multi_scene_script(
    past_topics: list[str] | None = None,
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a 15–25 second educational video script via OpenRouter.
    Falls back to Gemini generate_fact() if OpenRouter is unavailable.

    Args:
        past_topics: Optional list of past topic titles to avoid duplicates.
            If ``None``, an empty string is used for the prompt.
        history: Optional already-loaded history dict for duplicate checks.
            If ``None``, history is loaded from disk. Callers that already
            have ``history`` (e.g. the main pipeline) should pass it through
            to avoid a redundant second disk read.

    Returns:
        Dict with keys: category, title, fact_short, narration, caption,
        image_prompt, slides.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if is_unset_secret(api_key, PLACEHOLDER_OPENROUTER_KEY):
        log.info("OPENROUTER_API_KEY not set — using Gemini fallback for fact generation.")
        return fallback_gemini_fact(past_topics, history=history)

    past_topics_str = ", ".join(past_topics[-150:]) if past_topics else "None"
    # Only load history from disk if the caller did not pass it in. The main
    # pipeline already loads history, so this avoids a redundant read.
    if history is None:
        history = load_history()

    system_prompt = (
        "You are a master viral TikTok short video producer. "
        "Output ONLY valid JSON with no markdown or extra text."
    )
    prompt = f"""
Generate 1 fascinating, high-retention 4-slide carousel script about an amazing fact.
Avoid topics related to: {past_topics_str}.

Respond ONLY with valid JSON:
{{
  "category": "Science | History | Space | Technology | Nature | Human Body",
  "title": "Shocking Title (max 5 words)",
  "fact_short": "Core fact in 1 sentence for history deduplication.",
  "caption": "Full social media caption with emojis and 5 highly targeted, dynamic hashtags trending in this specific niche.",
  "slides": [
    {{"text": "Hook/Title text for slide 1", "image_prompt": "Cinematic 3D render prompt for slide 1, 9:16 vertical composition."}},
    {{"text": "Context/Fact Part 1 for slide 2", "image_prompt": "Cinematic 3D render prompt for slide 2, 9:16 vertical composition."}},
    {{"text": "The mindblowing twist/Fact Part 2 for slide 3", "image_prompt": "Cinematic 3D render prompt for slide 3, 9:16 vertical composition."}},
    {{"text": "Call to action text (e.g., Follow for more daily facts!)", "image_prompt": "Cinematic 3D render prompt for slide 4, 9:16 vertical composition."}}
  ],
  "virality_score": 10
}}
"""

    for attempt in range(3):
        try:
            raw = call_openrouter_llm(prompt, system_prompt)
            # Strip markdown fences if the model wraps the JSON (defensive only)
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)

            title = data.get('title', '')
            fact_short = data.get('fact_short', '')
            score = data.get('virality_score', 10)

            if is_duplicate(history, title, fact_short):
                log.warning(f"Generated duplicate fact '{title}' — regenerating (attempt {attempt+1}/3)…")
                continue

            if score < 7:
                log.info(f"Virality score {score}/10 is low — regenerating for better content (attempt {attempt+1}/3)…")
                continue

            log.info(
                f"Script generated via OpenRouter ✓ [{data.get('category')}] "
                f'"{title}"'
            )
            return data
        except Exception as e:
            log.warning(f"OpenRouter script generation failed on attempt {attempt+1} ({e})")

    log.warning("All attempts failed or resulted in low score/duplicates — using Gemini fallback.")
    return fallback_gemini_fact(past_topics, history=history)
