"""
Video builder: converts a static image card into a 9:16 TikTok-ready MP4.

Improvements over the original:
- FFmpeg availability check with clear install instructions
- Detects audio file duration via ffprobe → auto-matches video length
- Ken Burns subtle zoom-in effect for cinematic motion on static image
- Fade in (0.5 s) and fade out (0.5 s) applied via FFmpeg filter chain
- Native 9:16 input (image_size="vertical") skips the blur-pad step entirely
- -movflags +faststart for web-optimized MP4
- Uses logger instead of print()
"""
import os
import shutil
import subprocess
from typing import Optional

from logger import get_logger

log = get_logger()


def _check_ffmpeg() -> None:
    """Raise EnvironmentError with install instructions if ffmpeg is not on PATH."""
    if shutil.which("ffmpeg") is None:
        raise EnvironmentError(
            "ffmpeg is not installed or not on PATH.\n"
            "  Windows: winget install Gyan.FFmpeg\n"
            "            (then restart your terminal)\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   sudo apt install ffmpeg"
        )


def _get_audio_duration(audio_path: str) -> float:
    """Return audio duration in seconds via ffprobe. Returns 0.0 on failure."""
    if not shutil.which("ffprobe"):
        return 0.0
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except Exception as e:
        log.warning(f"ffprobe duration check failed ({e}) — using fallback duration.")
        return 0.0


def image_to_video(
    image_path: str,
    output_video_path: str = "output/daily_fact_video.mp4",
    duration: int = 12,
    audio_path: Optional[str] = None,
    image_size: str = "square",
    ken_burns: bool = True,
) -> str:
    """
    Convert a static image card into a 9:16 vertical MP4.

    Args:
        image_path:         Source image (PNG).
        output_video_path:  Destination MP4.
        duration:           Fallback duration in seconds if no audio is provided.
        audio_path:         Optional MP3/WAV; video length will match audio if given.
        image_size:         "square" (1080×1080) or "vertical" (1080×1920).
                            "vertical" skips the blur-pad step.
        ken_burns:          Apply subtle zoom-in motion effect (default True).

    Returns:
        Path to the saved MP4 file.

    Raises:
        EnvironmentError: If ffmpeg is not installed.
        RuntimeError:     If ffmpeg exits with a non-zero return code.
    """
    _check_ffmpeg()
    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)

    has_audio = bool(audio_path and os.path.exists(audio_path))

    # ── Determine actual video duration ───────────────────────────
    if has_audio:
        audio_dur = _get_audio_duration(audio_path)
        video_dur = max(audio_dur + 0.5, 5.0)   # add 0.5 s tail after speech ends
    else:
        video_dur = float(duration)

    total_frames   = int(video_dur * 30)
    fade_dur       = 0.5                             # seconds for each fade
    fade_out_start = max(video_dur - fade_dur, 0.0)

    # ── Build FFmpeg video filter chain ───────────────────────────
    if image_size == "vertical":
        # Native 9:16 input — just scale and apply effects
        vf_parts = ["scale=1080:1920:flags=lanczos"]
        if ken_burns:
            vf_parts.append(
                f"zoompan="
                f"z='min(zoom+0.0008,1.20)':"
                f"d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"s=1080x1920:fps=30"
            )
        vf_parts += [
            f"fade=t=in:st=0:d={fade_dur}",
            f"fade=t=out:st={fade_out_start:.3f}:d={fade_dur}",
        ]
        vf_filter = ",".join(vf_parts)

    else:
        # Square (1080×1080) → blur-pad to 9:16, then effects
        pad_steps = (
            "split[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,gblur=sigma=30[bg_blur];"
            "[fg]scale=1080:1080[fg_scaled];"
            "[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2"
        )
        effects = []
        if ken_burns:
            effects.append(
                f"zoompan="
                f"z='min(zoom+0.0008,1.20)':"
                f"d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"s=1080x1920:fps=30"
            )
        effects += [
            f"fade=t=in:st=0:d={fade_dur}",
            f"fade=t=out:st={fade_out_start:.3f}:d={fade_dur}",
        ]
        vf_filter = pad_steps + "," + ",".join(effects)

    # ── Assemble FFmpeg command ────────────────────────────────────
    cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", image_path]

    if has_audio:
        cmd += ["-i", audio_path]

    cmd += [
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "medium",
    ]

    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-t", str(video_dur)]

    cmd += ["-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", output_video_path]

    log.info(
        f"Creating 9:16 video — source: {image_size}, "
        f"ken_burns: {ken_burns}, duration: ~{video_dur:.1f}s"
    )
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        # Show last 2000 chars of stderr for diagnostics
        log.error(f"FFmpeg error output:\n{result.stderr[-2000:]}")
        raise RuntimeError(
            "Video creation failed. Check the log above for FFmpeg error details."
        )

    size_mb = os.path.getsize(output_video_path) / 1_048_576
    log.info(f"Video saved → {output_video_path} ({size_mb:.1f} MB)")
    return output_video_path


if __name__ == "__main__":
    _img = "output/daily_fact_card.png"
    _audio = "output/narration.mp3"
    if os.path.exists(_img):
        image_to_video(
            _img,
            "output/test_video.mp4",
            duration=12,
            audio_path=_audio if os.path.exists(_audio) else None,
        )
