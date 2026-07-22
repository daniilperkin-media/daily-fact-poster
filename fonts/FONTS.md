# Bundled Fonts for Daily Fact Poster

Place TrueType font files in this directory to override system fonts in `graphic_builder.py`.

## Recommended: Inter (SIL Open Font License — 100% Free)

Inter is a free, open-source typeface optimized for screens, used by Notion, GitHub, and many modern apps.

**Download:** https://fonts.google.com/specimen/Inter  
*(Click "Download family" → extract → find the .ttf files)*

**Files to place here:**
- `Inter-Bold.ttf`     ← used for title and badge text
- `Inter-Regular.ttf`  ← used for body fact text and watermark

## How the font resolution works

`graphic_builder.py` searches for fonts in this order:

1. `fonts/Inter-Bold.ttf` / `fonts/Inter-Regular.ttf` ← **best quality**
2. `C:/Windows/Fonts/segoeui.ttf` (Windows)
3. `C:/Windows/Fonts/arial.ttf` (Windows)
4. `/System/Library/Fonts/Supplemental/Arial.ttf` (macOS)
5. `/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf` (Linux)
6. `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` (Linux)
7. PIL default bitmap font ← **lowest quality (blurry at large sizes)**

Placing Inter fonts here guarantees identical output on all operating systems.

## Other good free alternatives

| Font         | Download                             | Notes                  |
|--------------|--------------------------------------|------------------------|
| Outfit       | fonts.google.com/specimen/Outfit     | Modern, geometric      |
| Poppins      | fonts.google.com/specimen/Poppins    | Rounded, friendly      |
| Space Grotesk| fonts.google.com/specimen/Space+Grotesk | Techy look          |

Just rename the downloaded files to `Inter-Bold.ttf` / `Inter-Regular.ttf`
(or update the path in `_get_font()` in `graphic_builder.py`).
