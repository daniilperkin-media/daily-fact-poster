"""
Neural voiceover generation using edge-tts (Microsoft Neural TTS, free).

Improvements over the original:
- Handles nested event loops (e.g. Jupyter) via nest_asyncio or subprocess fallback
- Voice is configurable via TTS_VOICE env var (no code change needed)
- Validates output file exists and has non-zero size after generation
- Uses logger instead of print()
"""
import asyncio
import os

from logger import get_logger

log = get_logger()

try:
    import edge_tts
    _EDGE_TTS_AVAILABLE = True
except ImportError:
    _EDGE_TTS_AVAILABLE = False
    log.warning("edge-tts not installed. Run: pip install edge-tts")


async def _generate_voice_async(text: str, output_path: str, voice: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_voiceover(
    text: str,
    output_path: str = "output/narration.mp3",
    voice: str = None,
) -> str:
    """
    Generate a neural TTS voiceover MP3 via Microsoft edge-tts.

    Args:
        text:        Script text to synthesize.
        output_path: Destination MP3 file path.
        voice:       edge-tts voice name. Overrides the TTS_VOICE env var.
                     Default: en-US-ChristopherNeural
                     Other options:
                       en-US-AriaNeural      (female, energetic)
                       en-GB-RyanNeural      (British male)
                       en-AU-NatashaNeural   (Australian female)
                       en-US-GuyNeural       (male, authoritative)

    Returns:
        Absolute path to the saved MP3 file.

    Raises:
        ImportError:  If edge-tts is not installed.
        RuntimeError: If the output file is missing or empty after generation.
    """
    if not _EDGE_TTS_AVAILABLE:
        raise ImportError("edge-tts is not installed. Run: pip install edge-tts")

    selected_voice = voice or os.environ.get("TTS_VOICE", "en-US-ChristopherNeural")
    log.info(f"Generating voiceover (voice='{selected_voice}')…")

    coro = _generate_voice_async(text, output_path, selected_voice)

    # Detect if we're already inside a running event loop (e.g. Jupyter)
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        # Try nest_asyncio to patch the running loop
        try:
            import nest_asyncio
            nest_asyncio.apply()
            running_loop.run_until_complete(coro)
        except ImportError:
            # Final fallback: spawn a fresh Python subprocess to run edge-tts
            log.warning(
                "nest_asyncio not available — spawning subprocess for TTS generation."
            )
            import subprocess
            import sys
            script = (
                "import asyncio, edge_tts, os\n"
                f"async def _run():\n"
                f"    os.makedirs(os.path.dirname(os.path.abspath({output_path!r})), exist_ok=True)\n"
                f"    c = edge_tts.Communicate({text!r}, {selected_voice!r})\n"
                f"    await c.save({output_path!r})\n"
                "asyncio.run(_run())\n"
            )
            subprocess.run([sys.executable, "-c", script], check=True)
    else:
        asyncio.run(coro)

    # Validate output
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(
            f"edge-tts produced no audio at '{output_path}'. "
            "Check your internet connection and that the voice name is valid."
        )

    size_kb = os.path.getsize(output_path) / 1024
    log.info(f"Voiceover saved → {output_path} ({size_kb:.0f} KB)")
    return output_path


if __name__ == "__main__":
    generate_voiceover(
        "Did you know honey found in ancient Egyptian tombs is still edible after 3,000 years?",
        "output/test_voice.mp3",
    )
