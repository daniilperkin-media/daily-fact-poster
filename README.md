# 💡 Daily Fact Poster

An automated AI pipeline that generates a daily fact card + TikTok video and publishes to **TikTok, Telegram, Discord, Threads, Instagram, and X** — all from a single command.

---

## Architecture

```
main.py
  │
  ├── [2] fact_generator.py      ← Gemini 2.0 Flash (or OpenRouter/DeepSeek R1)
  │                                 Virality self-score; regenerates if score < 7
  │
  ├── [3] image_generator.py     ← Pollinations.ai (free, no key)
  │                                 Random seed, content-type validation, retry
  │
  ├── [4] graphic_builder.py     ← PIL: gradient overlay, pixel-accurate text wrap
  │                                 Supports "square" (1080×1080) and "vertical" (1080×1920)
  │
  ├── [5] voice_generator.py     ← edge-tts (Microsoft Neural TTS, free)
  │   video_builder.py           ← FFmpeg: Ken Burns zoom, fade in/out, 9:16 MP4
  │
  ├── [6] uploader.py            ← AWS S3 → tmpfiles.org fallback
  │
  └── [7] poster.py              ← Make.com webhook (Threads / Instagram / X)
      tiktok_poster.py           ← TikTok API + publish_id polling
      (Telegram, Discord inline) ← Direct Bot API / webhook
```

**Support modules:**
- `logger.py` — structured timestamps to stdout + rotating `logs/pipeline.log`
- `http_utils.py` — GET/POST with automatic retry + exponential backoff
- `history_manager.py` — de-duplication history capped at 200 topics + stats

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install FFmpeg (system dependency)

```bash
# Windows (requires winget / Windows Package Manager)
winget install Gyan.FFmpeg

# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 4. (Optional) Install bundled fonts

Download **Inter** from https://fonts.google.com/specimen/Inter and place
`Inter-Bold.ttf` + `Inter-Regular.ttf` in the `fonts/` directory.
See `fonts/FONTS.md` for details and alternatives.

### 5. Run

```bash
# Dry run — full pipeline locally, no posts sent
python main.py --dry-run

# Production — generate and post everywhere
python main.py

# Fast image-only run (no TTS / FFmpeg needed)
python main.py --no-video

# Generate both 1:1 square and 9:16 vertical cards
python main.py --multi-format

# TikTok + Make.com only
python main.py --no-telegram --no-discord
```

---

## Environment Variables

| Variable               | Required | Description |
|------------------------|----------|-------------|
| `GEMINI_API_KEY`       | Yes*     | Google Gemini API key for fact generation |
| `OPENROUTER_API_KEY`   | No       | OpenRouter key for DeepSeek R1 (richer scripts) |
| `TEXT_MODEL`           | No       | OpenRouter model slug (default: `deepseek/deepseek-r1`) |
| `OPENROUTER_REFERER`   | No       | HTTP-Referer for OpenRouter (default: `https://github.com`) |
| `OPENROUTER_TITLE`     | No       | X-Title for OpenRouter (default: `Daily Fact Poster`) |
| `TTS_VOICE`            | No       | edge-tts voice name (default: `en-US-ChristopherNeural`) |
| `TIKTOK_ACCESS_TOKEN`  | No       | TikTok user access token for direct posting |
| `TIKTOK_CLIENT_KEY`    | No       | TikTok Client Key (alternative auth method) |
| `TIKTOK_CLIENT_SECRET` | No       | TikTok Client Secret |
| `TELEGRAM_BOT_TOKEN`   | No       | Telegram Bot API token |
| `TELEGRAM_CHAT_ID`     | No       | Telegram channel handle or ID |
| `DISCORD_WEBHOOK_URL`  | No       | Discord channel webhook URL |
| `MAKE_WEBHOOK_URL`     | No       | Make.com webhook for Threads / Instagram / X |
| `AWS_ACCESS_KEY_ID`    | No       | AWS IAM key for S3 upload |
| `AWS_SECRET_ACCESS_KEY`| No       | AWS IAM secret |
| `AWS_REGION`           | No       | S3 bucket region (default: `us-east-1`) |
| `AWS_S3_BUCKET`        | No       | S3 bucket name |

*If `GEMINI_API_KEY` is unset, the pipeline falls back to a hardcoded sample fact.

---

## Scheduling (Windows)

Run `scheduler_windows.bat` **as Administrator** once to register a Windows Task Scheduler job that runs `main.py` every day at 9:00 AM:

```batch
scheduler_windows.bat
```

Manual control:
```batch
schtasks /run    /tn "DailyFactPoster"          # run immediately
schtasks /query  /tn "DailyFactPoster"          # check status
schtasks /change /tn "DailyFactPoster" /st 08:00  # change time
schtasks /delete /tn "DailyFactPoster" /f       # remove
```

---

## Make.com Webhook Setup

1. Sign up at [make.com](https://www.make.com/) (free tier available)
2. Create a new Scenario → add a **Custom Webhook** trigger module
3. Copy the Webhook URL into `.env` as `MAKE_WEBHOOK_URL`
4. Add action modules: Threads, Instagram for Business, Twitter/X, Telegram Channel
5. Map `1.caption` and `1.image_url` to each social action

The webhook payload structure:

```json
{
  "title":     "Fact headline",
  "fact":      "One sentence fact",
  "category":  "Science",
  "caption":   "Full caption with emojis and hashtags",
  "image_url": "https://...",
  "source":    "Daily_Fact_Poster"
}
```

---

## File Structure

```
Daily_Fact_Poster/
├── main.py                   ← Unified pipeline entry point (use this)
├── generate_and_post.py      ← Deprecated shim → delegates to main.py
├── fact_generator.py         ← Gemini fact generation
├── script_generator.py       ← OpenRouter/DeepSeek video script generation
├── image_generator.py        ← Pollinations.ai image generation
├── graphic_builder.py        ← PIL graphic card compositor
├── video_builder.py          ← FFmpeg 9:16 video builder
├── voice_generator.py        ← edge-tts neural voiceover
├── tiktok_poster.py          ← TikTok API posting + status polling
├── uploader.py               ← S3 / tmpfiles.org upload
├── poster.py                 ← Make.com webhook
├── logger.py                 ← Structured logging
├── http_utils.py             ← HTTP retry/backoff helpers
├── history_manager.py        ← Post history & de-duplication
├── openrouter_client.py      ← OpenRouter API client
├── history.json              ← Post history (committed for CI persistence)
├── fonts/                    ← Place Inter-Bold.ttf / Inter-Regular.ttf here
│   └── FONTS.md
├── output/                   ← Generated files (gitignored)
├── logs/                     ← Pipeline logs (gitignored)
├── .env                      ← Your credentials (gitignored)
├── .env.example              ← Template with all variables documented
├── requirements.txt
├── scheduler_windows.bat     ← Windows Task Scheduler setup
└── .gitignore
```
