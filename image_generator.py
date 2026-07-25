"""
AI image generation via OpenRouter's Image API (e.g., Flux 2 Pro).

Outputs images tailored for TikTok Photo Mode carousels (9:16 vertical).
"""
import base64
import os
import re
from typing import Literal

import requests

from logger import get_logger

log = get_logger()

SizeMode = Literal["square", "vertical"]


def _decode_and_save(content: str, output_path: str) -> None:
    """Extracts an image URL or base64 from OpenRouter response and saves it."""
    # 1. Try to find a URL
    url_match = re.search(r'(https?://[^\s)\]]+)', content)
    if url_match:
        url = url_match.group(1)
        log.info(f"Downloading image from {url}...")
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(res.content)
        return

    # 2. Try to decode base64
    # Sometimes it comes as raw base64 or data:image/png;base64,...
    b64_data = content
    if "base64," in content:
        b64_data = content.split("base64,")[1]
    
    # Strip markdown or extra quotes if present
    b64_data = re.sub(r'[^A-Za-z0-9+/=]', '', b64_data)
    
    try:
        image_bytes = base64.b64decode(b64_data)
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        return
    except Exception as e:
        raise ValueError(f"Could not parse image URL or base64 from response. Error: {e}")


def generate_image(
    prompt: str,
    output_path: str = "output/raw_image.png",
    size: SizeMode = "vertical",
    model: str = "black-forest-labs/flux.2-pro"
) -> str:
    """
    Generate an image from a text prompt via OpenRouter and save it locally.

    Args:
        prompt:      Descriptive text for the image.
        output_path: Destination file path.
        size:        "square" or "vertical".
        model:       The OpenRouter image model to use.

    Returns:
        Absolute path to the saved image file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    
    if not api_key or api_key.startswith("sk-or-v1-your_"):
        raise ValueError("OPENROUTER_API_KEY is missing or invalid.")

    # Flux 2 Pro supports aspect_ratio parameter
    # Wait, the Chat Completions API standard for OpenRouter image models:
    # prompt in messages, but we can't easily pass aspect_ratio in standard chat completion.
    # We will just append the aspect ratio requirement to the prompt to be safe.
    aspect_ratio_text = "9:16 vertical orientation" if size == "vertical" else "1:1 square orientation"
    enhanced_prompt = f"{prompt}, high quality, cinematic, 8k resolution, highly detailed, {aspect_ratio_text}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://github.com"),
        "X-Title": os.environ.get("OPENROUTER_TITLE", "Daily Fact Poster"),
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": enhanced_prompt}
        ],
        "modalities": ["image"]
    }

    log.info(f"Generating {size} image via {model}…")
    
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=90,
    )
    
    if res.status_code != 200:
        raise RuntimeError(f"OpenRouter API failed: {res.text}")
        
    data = res.json()
    
    if "choices" not in data or not data["choices"]:
        raise RuntimeError(f"Invalid response from OpenRouter: {data}")
        
    message = data["choices"][0]["message"]
    content = message.get("content")
    
    # OpenRouter's Image API sometimes returns the image inside the `images` array rather than `content`
    if not content and "images" in message:
        images = message["images"]
        if images and isinstance(images, list):
            image_url_obj = images[0].get("image_url")
            if image_url_obj and "url" in image_url_obj:
                content = image_url_obj["url"]
                
    if not content:
        raise RuntimeError(f"No content or image URL found in OpenRouter response: {data}")
    
    _decode_and_save(content, output_path)

    size_kb = os.path.getsize(output_path) / 1024
    log.info(f"Image saved → {output_path} ({size_kb:,.0f} KB)")
    
    return output_path

if __name__ == "__main__":
    generate_image(
        "A glowing golden honey jar inside an ancient Egyptian pyramid tomb",
        "output/test_image.png",
        size="vertical"
    )
