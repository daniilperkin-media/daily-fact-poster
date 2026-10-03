"""Offline end-to-end smoke test: script → images → cards → ffmpeg (no network).

Mocks script and image generation, stubs only the PowerShell clipboard call,
and runs run_pipeline(dry_run=True) against a temporary output directory with
the real FFmpeg and the real card builder. Skipped when ffmpeg is unavailable.
"""
import shutil
import subprocess as subprocess_module

import pytest
from PIL import Image

from daily_fact_poster import pipeline

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def _fake_fact(**overrides):
    fact = {
        "category": "Science",
        "title": "Smoke Test Fact",
        "fact_short": "A short fact for the smoke test.",
        "caption": "Smoke test caption #fact",
        "slides": [
            {"text": "Slide one", "image_prompt": "prompt one"},
            {"text": "Slide two", "image_prompt": "prompt two"},
        ],
        "virality_score": 10,
    }
    fact.update(overrides)
    return fact


def _fake_image(prompt, output_path, size="vertical"):
    Image.new("RGB", (64, 96), (10, 20, 30)).save(output_path)
    return output_path


@pytest.fixture
def smoke_env(tmp_path, monkeypatch):
    """Point the pipeline at a temp output dir and stub network + clipboard."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-smoke-test-key")
    monkeypatch.setattr(pipeline, "_OUTPUT_DIR", str(tmp_path / "output"))

    real_run = subprocess_module.run

    def fake_run(cmd, **kwargs):
        if cmd and cmd[0] == "powershell":
            return subprocess_module.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    return tmp_path


@needs_ffmpeg
def test_dry_run_builds_video(smoke_env, monkeypatch):
    monkeypatch.setattr(pipeline, "generate_multi_scene_script", lambda *a, **k: _fake_fact())
    monkeypatch.setattr(pipeline, "generate_image", _fake_image)

    assert pipeline.run_pipeline(dry_run=True, with_tiktok=False) is True

    output = smoke_env / "output"
    video = output / "carousel_video.mp4"
    assert video.exists() and video.stat().st_size > 0
    assert (output / "card_slide_1.jpg").exists()
    assert (output / "card_slide_2.jpg").exists()


@needs_ffmpeg
def test_fallback_fact_still_builds_video(smoke_env, monkeypatch):
    """A fallback fact (no slides) must be synthesised into a real carousel."""
    fact = _fake_fact()
    fact.pop("slides")
    monkeypatch.setattr(pipeline, "generate_multi_scene_script", lambda *a, **k: fact)
    monkeypatch.setattr(pipeline, "generate_image", _fake_image)

    assert pipeline.run_pipeline(dry_run=True, with_tiktok=False) is True
    output = smoke_env / "output"
    assert (output / "carousel_video.mp4").exists()
    assert (output / "card_slide_2.jpg").exists()
