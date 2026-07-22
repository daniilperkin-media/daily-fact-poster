import os
import json
import re
import requests
from typing import Dict, Any, List

def generate_fact(past_topics: List[str] = None) -> Dict[str, Any]:
    """
    Generates a daily interesting fact using Google Gemini API.
    Returns a dictionary containing title, short fact text, full caption, and image prompt.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[WARNING] GEMINI_API_KEY missing. Returning fallback sample fact for testing.")
        return {
            "category": "Science",
            "title": "Ancient Honey Discovery",
            "fact_short": "Honey found inside 3,000-year-old Egyptian tombs is still 100% edible today due to its low moisture and acidic pH.",
            "caption": "🍯 Mind-blowing science fact of the day!\n\nDid you know honey never spoils? Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly edible.\n\n#DailyFact #DidYouKnow #ScienceFacts #FunFacts",
            "image_prompt": "A glowing golden honey jar inside an ancient Egyptian pyramid tomb, 3d digital render, cinematic lighting"
        }

    past_topics_str = ", ".join(past_topics[-30:]) if past_topics else "None"

    prompt = f"""
You are a viral social media content creator specializing in fascinating, verified facts.
Generate 1 mind-blowing fact of the day.

Avoid topics related to: {past_topics_str}.

You MUST respond strictly with valid JSON with the following structure:
{{
  "category": "Space / Science / History / Nature / Technology / Human Body",
  "title": "Short punchy title (max 4-5 words)",
  "fact_short": "Core mind-blowing fact written in 1-2 clear, impactful sentences (max 30 words) for an image graphic card.",
  "caption": "Full engaging social media post caption with emojis, explanation, and 5 relevant hashtags.",
  "image_prompt": "Detailed AI image generation prompt describing a cinematic 3D visual representing this fact (no text in image, rich colors, high detail)."
}}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        text_content = res_json['candidates'][0]['content']['parts'][0]['text']
        cleaned_text = re.sub(r"^```json\s*|\s*```$", "", text_content.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned_text)
        return data
    except Exception as e:
        print(f"[WARNING] Gemini API request failed ({e}). Using sample fact fallback.")
        return {
            "category": "Science",
            "title": "Ancient Honey Discovery",
            "fact_short": "Honey found inside 3,000-year-old Egyptian tombs is still 100% edible today due to its low moisture and acidic pH.",
            "caption": "🍯 Mind-blowing science fact of the day!\n\nDid you know honey never spoils? Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly edible.\n\n#DailyFact #DidYouKnow #ScienceFacts #FunFacts",
            "image_prompt": "A glowing golden honey jar inside an ancient Egyptian pyramid tomb, 3d digital render, cinematic lighting"
        }

if __name__ == "__main__":
    # Quick test if run directly
    try:
        fact_data = generate_fact()
        print(json.dumps(fact_data, indent=2))
    except Exception as err:
        print(f"Error: {err}")
