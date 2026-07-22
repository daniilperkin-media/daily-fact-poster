import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def build_graphic_card(
    background_path: str,
    title: str,
    fact_text: str,
    output_path: str = "output/daily_fact_card.png",
    watermark: str = "@dailyfacts"
) -> str:
    """
    Overlays a sleek, dark gradient and typography onto background_path to produce a clean 1080x1080 social media graphic card.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 1. Open background image & resize to 1080x1080
    if os.path.exists(background_path):
        base_img = Image.open(background_path).convert("RGBA").resize((1080, 1080))
    else:
        # Fallback dark gradient canvas
        base_img = Image.new("RGBA", (1080, 1080), (20, 24, 33, 255))

    # 2. Add dark translucent overlay for text contrast
    overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 160))
    composed = Image.alpha_composite(base_img, overlay)

    # 3. Create Draw context
    draw = ImageDraw.Draw(composed)

    # Font setup with fallback to default PIL font
    def get_font(size):
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    header_font = get_font(36)
    title_font = get_font(52)
    body_font = get_font(42)
    watermark_font = get_font(28)

    # 4. Draw Header Badge ("💡 FACT OF THE DAY")
    badge_text = "💡 FACT OF THE DAY"
    draw.rectangle([(80, 100), (450, 150)], fill=(255, 180, 0, 220))
    draw.text((100, 108), badge_text, fill=(20, 20, 20), font=header_font)

    # 5. Draw Title
    draw.text((80, 190), title.upper(), fill=(255, 255, 255), font=title_font)

    # 6. Draw Fact Body Text (Wrapped)
    wrapped_lines = textwrap.wrap(fact_text, width=32)
    y_offset = 320
    for line in wrapped_lines:
        # Subtle drop shadow
        draw.text((82, y_offset + 2), line, fill=(0, 0, 0, 200), font=body_font)
        draw.text((80, y_offset), line, fill=(240, 240, 245), font=body_font)
        y_offset += 55

    # 7. Draw Watermark / Footer
    draw.line([(80, 960), (1000, 960)], fill=(255, 255, 255, 100), width=2)
    draw.text((80, 980), watermark, fill=(180, 190, 200, 200), font=watermark_font)

    # Save final RGB PNG
    final_rgb = composed.convert("RGB")
    final_rgb.save(output_path, "PNG", quality=95)
    print(f"Graphic card created at {output_path}")
    return output_path

if __name__ == "__main__":
    build_graphic_card(
        "output/test_image.png",
        "Ancient Discovery",
        "Honey found inside 3,000-year-old Egyptian tombs is still 100% edible today due to its low moisture and acidic pH.",
        "output/test_card.png"
    )
