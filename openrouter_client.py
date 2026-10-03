"""
OpenRouter LLM API client.

Improvements over the original:
- HTTP-Referer and X-Title are now configurable via env vars
  (OPENROUTER_REFERER, OPENROUTER_TITLE) instead of hardcoded GitHub URL
- Uses logger instead of print()
"""
import os

from constants import PLACEHOLDER_OPENROUTER_KEY, is_unset_secret
from http_utils import post_with_retry
from logger import get_logger

log = get_logger()


def call_openrouter_llm(
    prompt: str,
    system_prompt: str = "You are a professional social media video producer.",
    model: str | None = None,
) -> str:
    """
    Call OpenRouter's chat completions endpoint.

    Environment variables:
        OPENROUTER_API_KEY  — required
        TEXT_MODEL          — LLM model slug (default: openai/gpt-4o-mini)
        OPENROUTER_REFERER  — HTTP-Referer header (default: https://github.com)
        OPENROUTER_TITLE    — X-Title header (default: Daily Fact Poster)

    Returns:
        Raw text content from the first choice.

    Raises:
        ValueError: If the API key is missing or the response format is unexpected.
        requests.HTTPError: On non-2xx responses.
    """
    api_key      = os.environ.get("OPENROUTER_API_KEY", "").strip()
    target_model = model or os.environ.get("TEXT_MODEL", "openai/gpt-4o-mini")
    referer      = os.environ.get("OPENROUTER_REFERER", "https://github.com")
    title        = os.environ.get("OPENROUTER_TITLE",   "Daily Fact Poster")

    if is_unset_secret(api_key, PLACEHOLDER_OPENROUTER_KEY):
        raise ValueError("OPENROUTER_API_KEY is missing or still a placeholder in .env.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer":  referer,
        "X-Title":       title,
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       target_model,
        "messages":    [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }

    log.info(f"Calling OpenRouter ({target_model})…")
    # Route through http_utils so transient failures (429/5xx/network) get the
    # same retry + backoff treatment as every other API call in the pipeline.
    res = post_with_retry(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )

    try:
        return res.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(
            f"Unexpected OpenRouter response format: {e}\nRaw: {res.text[:500]}"
        ) from e
