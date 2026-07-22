"""
Graphic card builder using PIL/Pillow.

Major improvements over the original:
- Gradient overlay (transparent top → dark bottom) for cinematic depth
- Pixel-accurate text wrapping (not character-count) via textbbox measurement
- Dynamic badge width — no more clipped text
- Category-based accent colors for visual variety
- Supports both "square" (1080×1080) and "vertical" (1080×1920) canvas sizes
- Cross-platform font loading: bundled fonts/ dir → system fonts → PIL default
- Drop shadow on all text for legibility over bright images
- Accentuated divider line between title and body
"""
import os
from typing import Literal, Tuple

from PIL import Image, ImageDraw, ImageFont

from logger import get_logger

log = get_logger()

# ── Types ──────────────────────────────────────────────────────────────────────
SizeMode = Literal["square", "vertical"]

CANVAS_SIZES: dict[SizeMode, Tuple[int, int]] = {
    "square":   (1080, 1080),
    "vertical": (1080, 1920),
}

# Category → accent color (R, G, B)
CATEGORY_COLORS: dict[str, Tuple[int, int, int]] = {
    "Space":       (30,  130, 255),
    "Science":     (0,   200, 160),
    "History":     (220, 140,  20),
    "Nature":      (50,  185,  50),
    "Technology":  (140,  30, 230),
    "Human Body":  (225,  60,  60),
}
_DEFAULT_ACCENT: Tuple[int, int, int] = (255, 180, 0)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    Load a TrueType font at the given point size.
    Priority: bundled fonts/ → Windows system fonts → macOS → Linux → PIL default.
    """
    candidates = [
        # Bundled (user places Inter fonts here — see fonts/FONTS.md)
        os.path.join(_BASE_DIR, "fonts", "Inter-Bold.ttf"    if bold else "Inter-Regular.ttf"),
        os.path.join(_BASE_DIR, "fonts", "Inter-Bold.ttf"),     # fallback to bold if regular missing
        os.path.join(_BASE_DIR, "fonts", "Inter-Regular.ttf"),
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
    log.warning("No TrueType font found — falling back to PIL default bitmap font (quality will be low). "
                "Place Inter-Bold.ttf and Inter-Regular.ttf into the fonts/ directory for best results.")
    return ImageFont.load_default()


def _create_gradient_overlay(width: int, height: int) -> Image.Image:
    """
    Create a vertical RGBA gradient: fully transparent at the top, darkening
    toward the bottom (alpha ≈ 200 at the very bottom).
    Uses a 1-pixel-wide strip resized to full width for efficiency.
    """
    strip = Image.new("L", (1, height))
    pixels = strip.load()
    for y in range(height):
        t = y / height
        pixels[0, y] = int(200 * (t ** 0.65))  # non-linear ramp
    alpha_channel = strip.resize((width, height), Image.LANCZOS)
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
    Uses PIL's textbbox for accurate per-word measurement.
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
            # Graceful fallback: estimate ~10 px per character
            line_px = len(candidate) * (getattr(font, "size", 40) // 4)

        if line_px <= max_px:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)  # single word that overflows — accept it

    if current:
        lines.append(" ".join(current))
    return lines or [""]


# ── Public API ─────────────────────────────────────────────────────────────────

def build_graphic_card(
    background_path: str,
    title: str,
    fact_text: str,
    output_path: str = "output/daily_fact_card.png",
    watermark: str = "@dailyfacts",
    category: str = "",
    size: SizeMode = "square",
) -> str:
    """
    Composite a social media graphic card on top of an AI-generated background.

    Args:
        background_path: Path to the raw background image (any size — will be resized).
        title:           Short headline text.
        fact_text:       Body fact (1–2 sentences).
        output_path:     Destination PNG file path.
        watermark:       Handle / username displayed in the footer.
        category:        Fact category for accent badge color (e.g. "Space", "History").
        size:            "square" (1080×1080) or "vertical" (1080×1920).

    Returns:
        Path to the saved PNG file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    W, H = CANVAS_SIZES[size]

    # ── 1. Background ──────────────────────────────────────────────
    if os.path.exists(background_path):
        base = Image.open(background_path).convert("RGBA").resize((W, H), Image.LANCZOS)
    else:
        log.warning(f"Background not found: '{background_path}' — using dark canvas fallback.")
        base = Image.new("RGBA", (W, H), (18, 22, 32, 255))

    # ── 2. Gradient overlay ────────────────────────────────────────
    overlay = _create_gradient_overlay(W, H)
    composed = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(composed)

    # ── 3. Fonts ───────────────────────────────────────────────────
    MARGIN    = 72
    TEXT_W    = W - 2 * MARGIN          # usable pixel width for text

    font_badge = _get_font(30, bold=True)
    font_title = _get_font(56, bold=True)
    font_body  = _get_font(40, bold=False)
    font_mark  = _get_font(26, bold=False)

    # ── 4. Category badge ──────────────────────────────────────────
    accent = CATEGORY_COLORS.get(category, _DEFAULT_ACCENT)
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
    badge_y = int(H * 0.08)

    # Rounded rectangle (requires Pillow ≥ 8.2)
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

    # ── 5. Title ───────────────────────────────────────────────────
    title_lines  = _wrap_pixels(draw, title.upper(), font_title, TEXT_W)
    title_line_h = 68
    title_y      = badge_y + badge_h + 28

    for line in title_lines:
        # Drop shadow (slight offset in dark)
        draw.text((MARGIN + 2, title_y + 2), line, fill=(0, 0, 0, 160), font=font_title)
        draw.text((MARGIN,     title_y),     line, fill=(255, 255, 255), font=font_title)
        title_y += title_line_h

    # ── 6. Accent divider ──────────────────────────────────────────
    divider_y = title_y + 14
    draw.rectangle([MARGIN, divider_y, MARGIN + 64, divider_y + 4], fill=(*accent, 220))

    # ── 7. Body text ───────────────────────────────────────────────
    body_lines  = _wrap_pixels(draw, fact_text, font_body, TEXT_W)
    body_line_h = 54
    body_y      = divider_y + 22

    for line in body_lines:
        draw.text((MARGIN + 2, body_y + 2), line, fill=(0, 0, 0, 160), font=font_body)
        draw.text((MARGIN,     body_y),     line, fill=(232, 237, 245), font=font_body)
        body_y += body_line_h

    # ── 8. Footer watermark ────────────────────────────────────────
    footer_y = H - 58
    draw.line([(MARGIN, footer_y - 14), (W - MARGIN, footer_y - 14)],
              fill=(255, 255, 255, 50), width=1)
    draw.text((MARGIN, footer_y), watermark, fill=(165, 175, 190, 180), font=font_mark)

    # ── 9. Save ────────────────────────────────────────────────────
    final = composed.convert("RGB")
    final.save(output_path, "PNG", optimize=True)
    log.info(f"Graphic card ({size}, {W}×{H}) → {output_path}")
    return output_path


if __name__ == "__main__":
    for _size in ("square", "vertical"):
        build_graphic_card(
            "output/test_image.png",
            "Ancient Discovery",
            "Honey found inside 3,000-year-old Egyptian tombs is still 100% edible today due to its low moisture and acidic pH.",
            f"output/test_card_{_size}.png",
            size=_size,
            category="History",
        )
