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
from history_manager import load_history, is_duplicate
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

    past_topics_str = ", ".join(past_topics[-150:]) if past_topics else "None"
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
                
            if score <= 7:
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
    return fallback_gemini_fact(past_topics)
