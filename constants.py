"""
Shared constants for the Daily Fact Poster pipeline.

Centralizes values that previously lived as ad-hoc literals (or redaction
artifacts) scattered across four modules:

- The placeholder sentinel strings documented in ``.env.example``. Every
  module that reads a secret from the environment checks against the *same*
  convention here, instead of each file inventing (or redacting) its own,
  so a user who copies ``.env.example`` verbatim gets a clean fallback
  rather than an opaque 401 from a live API.
- The ``SizeMode`` type alias, previously duplicated verbatim in
  ``graphic_builder.py`` and ``image_generator.py``.
"""
from __future__ import annotations

from typing import Literal

# ── Image / canvas size mode ──────────────────────────────────────────────────
SizeMode = Literal["square", "vertical"]

# ── Placeholder secrets (must match .env.example) ─────────────────────────────
PLACEHOLDER_OPENROUTER_KEY = "sk-or-v1-your-openrouter-api-key"
PLACEHOLDER_GEMINI_KEY = "AIzaSy_your_gemini_api_key"


def is_unset_secret(value: str, placeholder: str) -> bool:
    """
    Return True if ``value`` is empty or matches the documented placeholder.

    A user who copies ``.env.example`` verbatim trips this check and gets a
    graceful fallback (sample fact / Gemini route) instead of sending
    placeholder text to a live API.

    Args:
        value:      The raw env-var value (already stripped by the caller).
        placeholder: The canonical placeholder string from ``.env.example``.

    Returns:
        True if the secret is unset or still a placeholder.
    """
    if not value:
        return True
    return value == placeholder or value.startswith(placeholder)
