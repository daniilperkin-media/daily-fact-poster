"""
Multi-scene TikTok video script generator using DeepSeek R1 via OpenRouter.
Falls back to Gemini fact_generator if OpenRouter is not configured.

Uses logger instead of print().
"""
import json
import os
import re
from typing import Any, Dict, List

from openrouter_client import call_openrouter_llm
from fact_generator import generate_fact as fallback_gemini_fact
from logger import get_logger

log = get_logger()


def generate_multi_scene_script(past_topics: List[str] = None) -> Dict[str, Any]:
    """
    Generate a 15–25 second educational video script via DeepSeek R1 / OpenRouter.
    Falls back to Gemini generate_fact() if OpenRouter is unavailable.

    Returns:
        Dict with keys: category, title, fact_short, narration, caption, image_prompt.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-or-v1-your_"):
        log.info("OPENROUTER_API_KEY not set — using Gemini fallback for fact generation.")
        return fallback_gemini_fact(past_topics)

    past_topics_str = ", ".join(past_topics[-30:]) if past_topics else "None"

    system_prompt = (
        "You are a master viral TikTok short video producer. "
        "Output ONLY valid JSON with no markdown or extra text."
    )
    prompt = f"""
Generate 1 fascinating, high-retention 15–25 second educational short script about an amazing fact.
Avoid topics related to: {past_topics_str}.

Respond ONLY with valid JSON:
{{
  "category": "Science | History | Space | Technology | Nature | Human Body",
  "title": "Shocking Title (max 5 words)",
  "fact_short": "Core fact in 1 sentence for visual graphic card.",
  "narration": "Full natural 15–20 second voiceover (~50 words). Engaging and mind-blowing.",
  "caption": "Full social media caption with emojis and 5 viral hashtags.",
  "image_prompt": "Cinematic 3D render prompt for main scene, 9:16 vertical composition."
}}
"""

    try:
        raw = call_openrouter_llm(prompt, system_prompt)
        # Strip markdown fences if the model wraps the JSON (defensive only)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        log.info(
            f"Script generated via OpenRouter ✓ [{data.get('category')}] "
            f'"{data.get("title")}"'
        )
        return data
    except Exception as e:
        log.warning(f"OpenRouter script generation failed ({e}) — using Gemini fallback.")
        return fallback_gemini_fact(past_topics)
