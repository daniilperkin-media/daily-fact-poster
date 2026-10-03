# Daily Fact Poster

Automated AI pipeline that generates a daily fact carousel (script → AI
background images → composited 1080×1920 cards → 9:16 MP4) and uploads it to
**TikTok** as a draft in your inbox — one command: `python main.py`.

## Pipeline

```
main.py (wrapper) → daily_fact_poster/pipeline.py
  [2] script_generator   OpenRouter GPT-4o-mini multi-scene script (Gemini / sample-fact fallback)
  [3] image_generator    OpenRouter Flux 2 Pro · 1080×1920 · per-slide dark-canvas fallback
  [4] graphic_builder    PIL gradient overlay + pixel-accurate text wrapping
  [5] FFmpeg             2.5 s per slide · libx264 · 30 fps · yuv420p
  [6] tiktok_poster      Content Posting API: inbox/Drafts upload + status poll + token refresh
```

Support modules (all in `daily_fact_poster/`): `constants` (placeholder
sentinels, `SizeMode`), `logger` (rotating `logs/daily_fact.log`), `http_utils`
(retry/backoff), `history_manager` (2000-topic de-dupe, `history.json`),
`openrouter_client`, `tiktok_auth` (OAuth + automatic refresh; re-auth via
`python -m daily_fact_poster.tiktok_auth`), `paths` (repo-root resolver).
`tools/get_tiktok_user_token.py` is the legacy token helper — prefer `tiktok_auth`.

## Quick start

```bash
pip install -r requirements.txt             # runtime dependencies
pip install -r requirements-dev.txt         # development: pytest, ruff
cp .env.example .env                        # then fill in your API keys
winget install Gyan.FFmpeg                  # or: brew install ffmpeg / sudo apt install ffmpeg

python main.py --dry-run                    # full run locally, nothing posted*
python main.py --no-tiktok                  # generate + record topic, skip TikTok
python main.py                              # generate AND post to TikTok
```

\* `--dry-run` still calls the paid generation APIs (one script call + one
image per slide); it only skips posting and the history update. FFmpeg must be
installed and on `PATH`.

Optional: place `Inter-Bold.ttf` + `Inter-Regular.ttf` in `fonts/` for
identical rendering on every OS (system fonts are the fallback — see
`fonts/FONTS.md`).

## Environment variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | Script (GPT-4o-mini) + image (Flux 2 Pro) generation. Without it, scripts fall back to Gemini/sample facts, but image generation stops the run early — required in practice. |
| `TEXT_MODEL` | OpenRouter script model slug (default `openai/gpt-4o-mini`) |
| `OPENROUTER_REFERER` / `OPENROUTER_TITLE` | Optional OpenRouter HTTP headers |
| `GEMINI_API_KEY` | Fallback fact generator when OpenRouter is unset |
| `TIKTOK_ACCESS_TOKEN` / `TIKTOK_REFRESH_TOKEN` | User token + refresh token; expired access tokens are refreshed automatically and the rotated pair is written back to `.env` |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | OAuth client credentials used by `tiktok_auth` |
| `TIKTOK_PRIVACY_LEVEL` | Direct-post privacy level (default `SELF_ONLY`) |

`.env.example` placeholder values are detected and ignored, so a copied
template can never hit the TikTok API with fake credentials.

## TikTok posting behaviour

- Uploads to your TikTok **inbox/Drafts** first (the documented flow);
  `SEND_TO_USER_INBOX` confirms delivery — open the app to finish the post.
  The caption is copied to your clipboard for you.
- Fallback **Direct Post**: unaudited API clients can only publish
  private-viewing content; public posts require TikTok's Content Posting API
  audit. The privacy level is validated against the account's allowed options
  and falls back to `SELF_ONLY` when not allowed.
- Access tokens expire after ~24 h. With `TIKTOK_REFRESH_TOKEN` set, refresh
  is automatic; re-run `python -m daily_fact_poster.tiktok_auth` only if the
  refresh token is missing or older than a year.

## Scheduling (Windows)

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
scheduler_windows.bat    # run once as Administrator
```

`scheduler_windows.bat` registers the Task Scheduler job "DailyFactPoster"
(9:00 AM daily, `/it`, prefers `.venv\Scripts\python.exe` when present). It is
**not** registered by default — do it once `.env` is configured and FFmpeg is
on `PATH`.

```batch
schtasks /run    /tn "DailyFactPoster"             # run immediately
schtasks /query  /tn "DailyFactPoster"             # check status
schtasks /change /tn "DailyFactPoster" /st 08:00   # change time
schtasks /delete /tn "DailyFactPoster" /f          # remove
```

The task appends console output to `logs/scheduler.log`; the pipeline itself
writes `logs/daily_fact.log`. Check both for the first few days.

## File structure

```
main.py                    ← entry point (`python main.py`)
daily_fact_poster/         ← pipeline package (pipeline.py orchestrates; paths.py = REPO_ROOT)
tools/                     ← legacy token helper (get_tiktok_user_token.py)
tests/                     ← pytest suite incl. offline end-to-end smoke test
tiktok_legal/              ← TikTok app legal pages (index / privacy / terms)
tiktok_app_icon.jpg        ← app icon asset for the TikTok developer portal
tiktok*.txt                ← site-verification file (public — keep at repo root)
fonts/                     ← optional bundled fonts (see FONTS.md)
history.json               ← post history (committed to git)
output/ · logs/ · .env     ← generated files / logs / credentials (all gitignored)
scheduler_windows.bat · ruff.toml · requirements.txt · requirements-dev.txt
.github/workflows/ci.yml   ← CI: compileall + ruff + pytest (py3.10/3.12 + Windows)
```

Local gates (identical to CI):
`python -m compileall -q .` → `python -m ruff check .` → `python -m pytest tests -q`.
