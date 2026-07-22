import os
import subprocess

def image_to_video(
    image_path: str,
    output_video_path: str = "output/daily_fact_video.mp4",
    duration: int = 5
) -> str:
    """
    Converts a static image card into a 5-second MP4 video formatted for TikTok (1080x1920 9:16 format with subtle zoom).
    """
    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)

    # FFmpeg command to pad 1080x1080 to vertical 1080x1920 (9:16) with blurred background & 5sec loop
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", "split[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg_blur];[fg]scale=1080:1080[fg_scaled];[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2",
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-r", "30",
        output_video_path
    ]

    print(f"Converting image card to 9:16 vertical TikTok video ({duration}s)...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"[ERROR] FFmpeg video creation failed: {result.stderr}")
        raise RuntimeError("Failed to create TikTok video file.")

    print(f"TikTok video created successfully at {output_video_path}")
    return output_video_path

if __name__ == "__main__":
    test_img = "output/daily_fact_card.png"
    if os.path.exists(test_img):
        image_to_video(test_img, "output/test_tiktok_video.mp4")
