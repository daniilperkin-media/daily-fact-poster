# Daily Fact Poster

An automated AI pipeline that generates a daily fact carousel (script, AI
background images, composited cards, and a 9:16 MP4) and uploads the video
to **TikTok** as a draft in your inbox (finish it in the app) — all from a
single command.

---

## Architecture

```
main.py  →  daily_fact_poster/pipeline.py
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
  ├── [5] FFmpeg slideshow      ← 2.5s per slide, libx264, 30fps, yuv420p
  │
  └── [6] tiktok_poster.py      ← TikTok Content Posting API (inbox/Drafts upload, status poll,
                                   automatic access-token refresh)
```

**Support modules** (all in the `daily_fact_poster/` package):
- `constants.py` — shared placeholder-sentinel constants and `SizeMode` type
- `logger.py` — structured timestamps to stdout + rotating `logs/<logger-name>.log` (default `logs/daily_fact.log`)
- `http_utils.py` — GET/POST with automatic retry + exponential backoff
- `history_manager.py` — de-duplication history capped at 2000 topics + stats
- `openrouter_client.py` — OpenRouter chat-completion API client
- `tiktok_auth.py` — TikTok OAuth helpers (interactive token acquisition + automatic refresh; run via `python -m daily_fact_poster.tiktok_auth`)
- `paths.py` — repository-root resolver (`REPO_ROOT`) shared by the other modules
- `tools/get_tiktok_user_token.py` — older one-click token helper (legacy; prefer `tiktok_auth.py`)

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

# Skip TikTok posting (still generates all assets and records the topic)
python main.py --no-tiktok
```

`--dry-run` still calls the paid generation APIs (one script call + one
image per slide); it only skips posting and the history update. FFmpeg must
be installed and on `PATH`.

---

## Environment Variables

| Variable               | Required | Description |
|------------------------|----------|-------------|
| `OPENROUTER_API_KEY`   | Yes*     | OpenRouter key for script generation (GPT-4o-mini) and image generation (Flux 2 Pro) |
| `TEXT_MODEL`           | No       | OpenRouter model slug for script generation (default: `openai/gpt-4o-mini`) |
| `OPENROUTER_REFERER`   | No       | HTTP-Referer for OpenRouter (default: `https://github.com`) |
| `OPENROUTER_TITLE`     | No       | X-Title for OpenRouter (default: `Daily Fact Poster`) |
| `GEMINI_API_KEY`       | No       | Google Gemini key (fallback for single-fact mode when OpenRouter is unset) |
| `TIKTOK_ACCESS_TOKEN`  | No       | TikTok user access token (auto-refreshed when expired) |
| `TIKTOK_CLIENT_KEY`    | No       | TikTok Client Key (used by `tiktok_auth.py` to obtain/refresh tokens) |
| `TIKTOK_CLIENT_SECRET` | No       | TikTok Client Secret (used by `tiktok_auth.py`) |
| `TIKTOK_REFRESH_TOKEN` | No       | Written by `tiktok_auth.py`; used to auto-refresh the access token |
| `TIKTOK_PRIVACY_LEVEL` | No       | TikTok post privacy level for direct posts (default: `SELF_ONLY`) |

*If `OPENROUTER_API_KEY` is unset, script generation falls back to a single
Gemini-generated fact (or a hardcoded sample fact if Gemini is also unset),
turned into a minimal 2-slide carousel. Image generation always needs
`OPENROUTER_API_KEY`, so a keyless run stops with a clear message before
spending any image API calls.

---

## TikTok posting behaviour

- The video is uploaded to your TikTok **inbox/Drafts** first (the documented
  upload flow). Delivery is confirmed by the `SEND_TO_USER_INBOX` status —
  open the TikTok app to finish the post; the caption is copied to your
  clipboard for you.
- If the inbox path is unavailable, the tool falls back to a **Direct Post**
  attempt. Unaudited API clients can only publish private-viewing content;
  public posts require TikTok's Content Posting API audit.
- `TIKTOK_PRIVACY_LEVEL` defaults to `SELF_ONLY`. For direct posts the value
  is checked against the account's allowed privacy options (creator info API)
  and falls back to `SELF_ONLY` when it is not allowed.
- Access tokens expire after ~24 h. When `TIKTOK_REFRESH_TOKEN` is set, an
  expired token is refreshed automatically and the rotated pair is written
  back to `.env`. Re-run `python -m daily_fact_poster.tiktok_auth` if the refresh token itself
  is missing or older than a year.
- The `.env.example` placeholder values are detected and ignored, so a copied
  template can never hit the TikTok API with fake credentials.

---

## Scheduling (Windows)

Prerequisites on the machine that runs the task:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

plus a `.env` with real API keys and FFmpeg on `PATH`.

Run `scheduler_windows.bat` **as Administrator** once to register a Windows
Task Scheduler job that runs `main.py` every day at 9:00 AM. The script
prefers `.venv\Scripts\python.exe` when it exists and registers the task with
`/it` (runs while you are logged on):

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

The task appends console output to `logs/scheduler.log`; the pipeline itself
writes `logs/daily_fact.log`. Check both for the first few days. The task is
**not** registered by default — registering it is a deliberate step to take
once `.env` is configured.

---

## File Structure

```
daily-fact-poster/
├── main.py                   ← Entry point wrapper (`python main.py` — use this)
├── daily_fact_poster/        ← Pipeline package
│   ├── pipeline.py           ← Orchestrator: full run + CLI
│   ├── constants.py          ← Shared placeholder sentinels + SizeMode type
│   ├── fact_generator.py     ← Gemini fact generation (fallback)
│   ├── script_generator.py   ← OpenRouter multi-scene script generation
│   ├── image_generator.py    ← OpenRouter Flux 2 Pro image generation
│   ├── graphic_builder.py    ← PIL graphic card compositor
│   ├── tiktok_poster.py      ← TikTok API posting + status polling
│   ├── tiktok_auth.py        ← OAuth token helpers + automatic access-token refresh
│   ├── openrouter_client.py  ← OpenRouter API client
│   ├── logger.py             ← Structured logging
│   ├── http_utils.py         ← HTTP retry/backoff helpers
│   ├── history_manager.py    ← Post history & de-duplication
│   └── paths.py              ← Repository-root resolver (REPO_ROOT)
├── tools/
│   └── get_tiktok_user_token.py  ← One-click token helper (legacy; prefer tiktok_auth.py)
├── tests/                    ← pytest test suite
├── tiktok_legal/             ← TikTok app legal pages (index/privacy/terms)
├── tiktok_app_icon.jpg       ← App icon asset for the TikTok developer portal
├── tiktok*.txt               ← TikTok developer site-verification file (public; keep at repo root)
├── .github/workflows/ci.yml  ← CI: compileall, ruff, pytest incl. offline E2E smoke (3.10/3.12 + Windows)
├── ruff.toml                 ← Ruff linter config
├── history.json              ← Post history (committed to git)
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
