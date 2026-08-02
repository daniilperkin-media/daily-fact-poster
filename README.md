# Daily Fact Poster

An automated AI pipeline that generates a daily fact carousel (script, AI
background images, composited cards, voiceover, and a 9:16 MP4) and publishes
the video to **TikTok** — all from a single command.

---

## Architecture

```
main.py
  │
  ├── [2] script_generator.py   ← OpenRouter GPT-4o-mini multi-scene script
  │                                (falls back to Gemini single-fact if no key)
  │
  ├── [3] image_generator.py    ← OpenRouter Flux 2 Pro (requires OPENROUTER_API_KEY)
  │                                Vertical 1080×1920, retry via http_utils
  │
  ├── [4] graphic_builder.py    ← PIL: gradient overlay, pixel-accurate text wrap
  │                                "vertical" (1080×1920) cards
  │
  ├── [5] voice_generator.py    ← edge-tts (Microsoft Neural TTS, free)
  │
  ├── [6] FFmpeg slideshow      ← 2.5s per slide, libx264, 30fps, yuv420p
  │
  └── [7] tiktok_poster.py      ← TikTok Content Posting API (video upload + poll)
```

**Support modules:**
- `constants.py` — shared placeholder-sentinel constants and `SizeMode` type
- `logger.py` — structured timestamps to stdout + rotating `logs/pipeline.log`
- `http_utils.py` — GET/POST with automatic retry + exponential backoff
- `history_manager.py` — de-duplication history capped at 2000 topics + stats
- `openrouter_client.py` — OpenRouter chat-completion API client
- `tiktok_auth.py` / `get_tiktok_user_token.py` — TikTok OAuth helpers
- `uploader.py` — S3 / tmpfiles.org upload (used by TikTok init)

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
# Development (pytest, ruff):
pip install -r requirements-dev.txt
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

# Production — generate and post to TikTok
python main.py

# Skip TikTok posting (still generates all assets)
python main.py --no-tiktok
```

---

## Environment Variables

| Variable               | Required | Description |
|------------------------|----------|-------------|
| `OPENROUTER_API_KEY`   | Yes*     | OpenRouter key for script generation (GPT-4o-mini) and image generation (Flux 2 Pro) |
| `TEXT_MODEL`           | No       | OpenRouter model slug for script generation (default: `openai/gpt-4o-mini`) |
| `OPENROUTER_REFERER`   | No       | HTTP-Referer for OpenRouter (default: `https://github.com`) |
| `OPENROUTER_TITLE`     | No       | X-Title for OpenRouter (default: `Daily Fact Poster`) |
| `GEMINI_API_KEY`       | No       | Google Gemini key (fallback for single-fact mode when OpenRouter is unset) |
| `TTS_VOICE`            | No       | edge-tts voice name (default: `en-US-ChristopherNeural`) |
| `TIKTOK_ACCESS_TOKEN`  | No       | TikTok user access token for direct posting |
| `TIKTOK_CLIENT_KEY`    | No       | TikTok Client Key (alternative auth method) |
| `TIKTOK_CLIENT_SECRET` | No       | TikTok Client Secret |
| `AWS_ACCESS_KEY_ID`    | No       | AWS IAM key for S3 upload |
| `AWS_SECRET_ACCESS_KEY`| No       | AWS IAM secret |
| `AWS_REGION`           | No       | S3 bucket region (default: `us-east-1`) |
| `AWS_S3_BUCKET`        | No       | S3 bucket name |

*If `OPENROUTER_API_KEY` is unset, the pipeline falls back to a single
Gemini-generated fact (or a hardcoded sample fact if Gemini is also unset).

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

## File Structure

```
Daily_Fact_Poster/
├── main.py                   ← Unified pipeline entry point (use this)
├── constants.py              ← Shared placeholder sentinels + SizeMode type
├── fact_generator.py         ← Gemini fact generation (fallback)
├── script_generator.py       ← OpenRouter multi-scene script generation
├── image_generator.py        ← OpenRouter Flux 2 Pro image generation
├── graphic_builder.py        ← PIL graphic card compositor
├── voice_generator.py        ← edge-tts neural voiceover
├── tiktok_poster.py          ← TikTok API posting + status polling
├── tiktok_auth.py            ← TikTok OAuth token helpers
├── get_tiktok_user_token.py  ← Interactive TikTok token acquisition
├── uploader.py               ← S3 / tmpfiles.org upload
├── openrouter_client.py      ← OpenRouter API client
├── logger.py                 ← Structured logging
├── http_utils.py             ← HTTP retry/backoff helpers
├── history_manager.py        ← Post history & de-duplication
├── tests/                    ← pytest test suite
├── ruff.toml                 ← Ruff linter config
├── history.json              ← Post history (committed for CI persistence)
├── fonts/                    ← Place Inter-Bold.ttf / Inter-Regular.ttf here
│   └── FONTS.md
├── output/                   ← Generated files (gitignored)
├── logs/                     ← Pipeline logs (gitignored)
├── .env                      ← Your credentials (gitignored)
├── .env.example              ← Template with all variables documented
├── requirements.txt          ← Runtime dependencies (pinned)
├── requirements-dev.txt      ← Development dependencies (pytest, ruff)
├── scheduler_windows.bat     ← Windows Task Scheduler setup
└── .gitignore
```
