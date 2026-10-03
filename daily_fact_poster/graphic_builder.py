"""
Graphic card builder using PIL/Pillow for TikTok Carousels.

Features:
- Gradient overlay (transparent top → dark bottom) for cinematic depth
- Pixel-accurate text wrapping (not character-count) via textbbox measurement
- Dynamic badge width — no more clipped text
- Supports multi-slide layouts (Title slides vs Body slides)
"""
import os

from PIL import Image, ImageDraw, ImageFont

from .constants import SizeMode
from .logger import get_logger
from .paths import REPO_ROOT

log = get_logger()

CANVAS_SIZES: dict[SizeMode, tuple[int, int]] = {
    "square":   (1080, 1080),
    "vertical": (1080, 1920),
}

# Category → accent color (R, G, B)
CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "Space":       (30,  130, 255),
    "Science":     (0,   200, 160),
    "History":     (220, 140,  20),
    "Nature":      (50,  185,  50),
    "Technology":  (140,  30, 230),
    "Human Body":  (225,  60,  60),
}
_DEFAULT_ACCENT: tuple[int, int, int] = (255, 180, 0)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    Load a TrueType font at the given point size.
    """
    candidates = [
        # Bundled
        os.path.join(REPO_ROOT, "fonts", "Inter-Bold.ttf" if bold else "Inter-Regular.ttf"),
        os.path.join(REPO_ROOT, "fonts", "Inter-Bold.ttf"),
        os.path.join(REPO_ROOT, "fonts", "Inter-Regular.ttf"),
        # Windows
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _create_gradient_overlay(width: int, height: int) -> Image.Image:
    """
    Create a vertical RGBA gradient: fully transparent at the top, darkening
    toward the bottom (alpha ≈ 210 at the very bottom).
    """
    strip = Image.new("L", (1, height))
    pixels = strip.load()
    for y in range(height):
        # Start gradient halfway down to keep the top clear for the subject
        t = max(0, (y - height/3) / (2*height/3))
        pixels[0, y] = int(210 * t)
    alpha_channel = strip.resize((width, height), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0))
    overlay.putalpha(alpha_channel)
    return overlay


def _wrap_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_px: int,
) -> list[str]:
    """
    Word-wrap text so that no rendered line exceeds max_px in pixel width.
    """
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join(current + [word])
        try:
            bbox = draw.textbbox((0, 0), candidate, font=font)
            line_px = bbox[2] - bbox[0]
        except Exception:
            line_px = len(candidate) * (getattr(font, "size", 40) // 4)

        if line_px <= max_px:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)

    if current:
        lines.append(" ".join(current))
    return lines or [""]


# ── Public API ─────────────────────────────────────────────────────────────────

def build_graphic_card(
    background_path: str,
    slide_text: str,
    output_path: str = "output/daily_fact_card.jpg",
    watermark: str = "@dailyfacts",
    category: str = "",
    size: SizeMode = "vertical",
    slide_index: int = 1,
    total_slides: int = 4
) -> str:
    """
    Composite a social media graphic card for a carousel.

    Args:
        background_path: Path to the raw background image.
        slide_text:      Text to display on the slide.
        output_path:     Destination PNG file path.
        watermark:       Handle / username displayed in the footer.
        category:        Fact category for accent badge color.
        size:            "square" (1080×1080) or "vertical" (1080×1920).
        slide_index:     1-indexed slide number.
        total_slides:    Total number of slides in the carousel.

    Returns:
        Path to the saved PNG file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    W, H = CANVAS_SIZES[size]

    if os.path.exists(background_path):
        base = Image.open(background_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    else:
        log.warning(f"Background not found: '{background_path}' — using dark canvas fallback.")
        base = Image.new("RGBA", (W, H), (18, 22, 32, 255))

    # Gradient overlay to make text pop
    overlay = _create_gradient_overlay(W, H)
    composed = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(composed)

    MARGIN = 72
    TEXT_W = W - 2 * MARGIN

    is_title_slide = (slide_index == 1 or slide_index == total_slides)

    font_badge = _get_font(30, bold=True)
    font_text  = _get_font(60 if is_title_slide else 48, bold=is_title_slide)
    font_mark  = _get_font(26, bold=False)

    accent = CATEGORY_COLORS.get(category, _DEFAULT_ACCENT)

    # ── Category badge (only on first slide) ────────────────────────
    badge_y = 0  # only assigned (and read) inside the slide_index == 1 block
    if slide_index == 1:
        badge_label = f"💡 {category.upper()}" if category else "💡 FACT OF THE DAY"
        try:
            bb = draw.textbbox((0, 0), badge_label, font=font_badge)
            badge_text_w = bb[2] - bb[0]
            badge_text_h = bb[3] - bb[1]
        except Exception:
            badge_text_w, badge_text_h = 280, 24

        badge_pad_x, badge_pad_y = 20, 12
        badge_w = badge_text_w + 2 * badge_pad_x
        badge_h = badge_text_h + 2 * badge_pad_y
        badge_y = int(H * 0.15)

        try:
            draw.rounded_rectangle(
                [MARGIN, badge_y, MARGIN + badge_w, badge_y + badge_h],
                radius=8,
                fill=(*accent, 230),
            )
        except AttributeError:
            draw.rectangle(
                [MARGIN, badge_y, MARGIN + badge_w, badge_y + badge_h],
                fill=(*accent, 230),
            )
        draw.text(
            (MARGIN + badge_pad_x, badge_y + badge_pad_y),
            badge_label,
            fill=(20, 20, 20),
            font=font_badge,
        )

    # ── Slide Text ──────────────────────────────────────────────────
    text_to_render = slide_text.upper() if is_title_slide else slide_text
    lines = _wrap_pixels(draw, text_to_render, font_text, TEXT_W)
    line_h = 75 if is_title_slide else 60

    # Position text lower on the screen for carousels (above caption area)
    total_text_h = len(lines) * line_h
    start_y = H - total_text_h - 200

    if slide_index == 1:
        # If it's the title slide, put it below the badge
        start_y = badge_y + 80

    for i, line in enumerate(lines):
        y_pos = start_y + (i * line_h)
        # Drop shadow
        draw.text((MARGIN + 3, y_pos + 3), line, fill=(0, 0, 0, 180), font=font_text)
        draw.text((MARGIN,     y_pos),     line, fill=(255, 255, 255), font=font_text)

    # ── Progress dots ──────────────────────────────────────────────
    dot_radius = 8
    dot_spacing = 24
    total_dots_width = (total_slides * dot_radius * 2) + ((total_slides - 1) * dot_spacing)
    dots_start_x = (W - total_dots_width) // 2
    dots_y = H - 120

    for i in range(total_slides):
        cx = dots_start_x + i * (dot_radius * 2 + dot_spacing) + dot_radius
        cy = dots_y
        fill_color = (*accent, 255) if i == (slide_index - 1) else (255, 255, 255, 100)
        draw.ellipse([cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius], fill=fill_color)

    # ── Footer watermark ───────────────────────────────────────────
    footer_y = H - 58
    draw.line([(MARGIN, footer_y - 14), (W - MARGIN, footer_y - 14)], fill=(255, 255, 255, 50), width=1)
    draw.text((MARGIN, footer_y), watermark, fill=(165, 175, 190, 180), font=font_mark)

    final = composed.convert("RGB")
    final.save(output_path, "JPEG", quality=95)
    log.info(f"Graphic slide {slide_index}/{total_slides} → {output_path}")
    return output_path
