# AGENTS.md — daily-fact-poster

Working rules for AI agents (and humans) in this repository. Human-facing
documentation lives in `README.md`.

## What this is

Python pipeline: daily fact script (OpenRouter GPT-4o-mini) → AI images
(Flux 2 Pro) → 1080×1920 PIL cards → 9:16 MP4 (FFmpeg) → upload to TikTok as
a draft. Entry point: `python main.py` (thin wrapper over
`daily_fact_poster/pipeline.py`). Requires Python 3.10+ and FFmpeg on `PATH`.

## Cautions

- **Never run `python main.py` without an explicit ask** — it generates AND
  posts to TikTok. Even `--dry-run` / `--no-tiktok` call the paid generation
  APIs (OpenRouter credits).
- **Never print, commit or invent secrets.** `.env` is gitignored
  (`OPENROUTER_API_KEY`, `TIKTOK_*`). The placeholder values in
  `.env.example` and `constants.py` are detected and ignored by design —
  keep them in sync when env vars change.
- **Do not delete runtime state**: `history.json`, `logs/`, `output/`.
- The `tiktok*.txt` verification file at the repo root must stay there for
  the public URL registration — do not move or edit it.

## Layout

- `daily_fact_poster/` — the pipeline package (`pipeline.py` orchestrates;
  tests import it as `from daily_fact_poster import ...`). `paths.py` is the
  single `REPO_ROOT` source for `logs/`, `fonts/`, `history.json`, `output/`
  and `.env`, all of which stay at the repo root.
- `tools/` — legacy one-click token helper; prefer
  `python -m daily_fact_poster.tiktok_auth`.
- `tests/` — pytest suite incl. an offline end-to-end smoke test (mocked
  network + clipboard, real PIL cards + FFmpeg; skips when FFmpeg is absent).

## Gates (identical to CI)

```bash
python -m compileall -q .
python -m ruff check .
python -m pytest tests -q
```

CI runs on every push to `main` and all PRs: Python 3.10 + 3.12 on Ubuntu,
plus a Windows 3.12 leg. It installs FFmpeg itself — GitHub runner images do
not ship it. All gates must pass before committing.

## Conventions

- Commit messages: plain English, explain the why; stage specific files
  (no `git add -A`).
- Never commit generated assets, `logs/`, `output/` or `.env`.
- Keep `README.md` and this file accurate when layout or commands change.
