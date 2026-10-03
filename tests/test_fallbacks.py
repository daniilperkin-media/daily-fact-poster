"""Tests for fallback slide synthesis (Gemini/sample fact → 2-slide carousel)."""
from daily_fact_poster import constants, fact_generator, script_generator


def test_fact_to_slides_uses_title_and_fact():
    slides = fact_generator.fact_to_slides(
        {"title": "T", "fact_short": "F", "image_prompt": "P"}
    )
    assert [s["text"] for s in slides] == ["T", "F"]
    assert all(s["image_prompt"] == "P" for s in slides)


def test_fact_to_slides_without_fact_text():
    slides = fact_generator.fact_to_slides({})
    assert slides[0]["text"] == "Did You Know?"
    assert len(slides) == 1


def test_missing_key_fallback_returns_slides(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", constants.PLACEHOLDER_OPENROUTER_KEY)
    monkeypatch.setattr(
        script_generator,
        "fallback_gemini_fact",
        lambda *a, **k: {"title": "T", "fact_short": "F", "image_prompt": "P"},
    )
    result = script_generator.generate_multi_scene_script([], history={})
    assert [s["text"] for s in result["slides"]] == ["T", "F"]
