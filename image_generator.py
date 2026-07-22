"""
AI image generation via Pollinations.ai (free, no key required).

Fixes over the original:
- Random seed on every call (was hardcoded seed=42 — same image every run)
- Content-Type validation before saving (catches HTML error pages / rate limits)
- Retry with backoff via http_utils
- Supports both square (1080x1080) and vertical (1080x1920) output sizes
"""
import os
import random
import urllib.parse
from typing import Literal

from http_utils import get_with_retry
from logger import get_logger

log = get_logger()

SizeMode = Literal["square", "vertical"]

_DIMENSIONS: dict[SizeMode, tuple[int, int]] = {
    "square":   (1080, 1080),
    "vertical": (1080, 1920),
}


def generate_image(
    prompt: str,
    output_path: str = "output/raw_image.png",
    size: SizeMode = "square",
) -> str:
    """
    Generate an image from a text prompt via Pollinations.ai and save it locally.

    Args:
        prompt:      Descriptive text for the image.
        output_path: Destination file path (PNG).
        size:        "square" (1080×1080) or "vertical" (1080×1920).

    Returns:
        Absolute path to the saved image file.

    Raises:
        RuntimeError: If the API returns a non-image content type (rate limit / error page).
        requests.RequestException: Propagated after all retries are exhausted.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    width, height = _DIMENSIONS[size]
    seed = random.randint(1, 999_999)   # randomized every call — was hardcoded 42

    encoded_prompt = urllib.parse.quote(f"{prompt}, high quality, cinematic, 8k, detailed")
    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={width}&height={height}&nologo=true&seed={seed}"
    )

    log.info(f"Generating {size} image via Pollinations.ai (seed={seed})…")
    response = get_with_retry(image_url, timeout=90, retries=3, backoff=8)

    # Validate that we actually received an image — not an HTML error page
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"Pollinations.ai returned '{content_type}' instead of an image.\n"
            f"The API may be rate-limited or down. Response preview: {preview}"
        )

    with open(output_path, "wb") as f:
        f.write(response.content)

    size_kb = len(response.content) / 1024
    log.info(f"Image saved → {output_path} ({size_kb:,.0f} KB, {width}×{height})")
    return output_path


if __name__ == "__main__":
    generate_image(
        "A glowing golden honey jar inside an ancient Egyptian pyramid tomb, 3d render",
        "output/test_image.png",
    )
