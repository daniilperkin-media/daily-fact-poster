"""
HTTP utility helpers with automatic retry and exponential backoff.
Wraps requests.get / requests.post so every network call in the pipeline
survives transient failures without crashing the whole run.

Usage:
    from http_utils import get_with_retry, post_with_retry
    response = get_with_retry("https://example.com/api", timeout=30)
    response = post_with_retry("https://example.com/api", json={...}, timeout=30)
"""
import time
from typing import Any

import requests

from logger import get_logger

log = get_logger()


def get_with_retry(
    url: str,
    *,
    retries: int = 3,
    backoff: float = 5.0,
    **kwargs: Any,
) -> requests.Response:
    """
    HTTP GET with automatic retry on any RequestException.

    Args:
        url:     Target URL.
        retries: Maximum number of attempts (default 3).
        backoff: Base backoff in seconds; wait = backoff * attempt (default 5 s).
        **kwargs: Passed verbatim to requests.get (timeout, headers, …).

    Returns:
        A successful requests.Response (2xx).

    Raises:
        requests.RequestException: Re-raised after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == retries:
                break
            wait = backoff * attempt
            log.warning(
                f"[HTTP GET] Attempt {attempt}/{retries} failed: {exc} "
                f"— retrying in {wait:.0f}s"
            )
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def post_with_retry(
    url: str,
    *,
    retries: int = 3,
    backoff: float = 5.0,
    **kwargs: Any,
) -> requests.Response:
    """
    HTTP POST with automatic retry on any RequestException.

    Args:
        url:     Target URL.
        retries: Maximum number of attempts (default 3).
        backoff: Base backoff in seconds; wait = backoff * attempt (default 5 s).
        **kwargs: Passed verbatim to requests.post (json, data, headers, …).

    Returns:
        A successful requests.Response (2xx).

    Raises:
        requests.RequestException: Re-raised after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == retries:
                break
            wait = backoff * attempt
            log.warning(
                f"[HTTP POST] Attempt {attempt}/{retries} failed: {exc} "
                f"— retrying in {wait:.0f}s"
            )
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]
