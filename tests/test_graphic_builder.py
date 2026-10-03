"""Tests for graphic_builder: pixel wrapping and the missing-background fallback."""
from PIL import Image, ImageDraw, ImageFont

from daily_fact_poster import graphic_builder


def _draw():
    return ImageDraw.Draw(Image.new("RGB", (10, 10)))


def test_wrap_pixels_wraps_long_text():
    lines = graphic_builder._wrap_pixels(
        _draw(), "one two three four five six seven", ImageFont.load_default(), max_px=60
    )
    assert len(lines) >= 2
    assert " ".join(lines).split() == "one two three four five six seven".split()


def test_wrap_pixels_keeps_oversized_single_word():
    lines = graphic_builder._wrap_pixels(
        _draw(), "supercalifragilisticexpialidocious", ImageFont.load_default(), max_px=10
    )
    assert lines == ["supercalifragilisticexpialidocious"]


def test_build_card_falls_back_to_dark_canvas(tmp_path):
    out = tmp_path / "card.jpg"
    graphic_builder.build_graphic_card(
        background_path=str(tmp_path / "missing.jpg"),
        slide_text="Hello world",
        output_path=str(out),
        category="Science",
        size="vertical",
        slide_index=2,
        total_slides=2,
    )
    assert out.exists()
    assert out.stat().st_size > 0
