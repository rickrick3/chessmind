# Chess Coach

Learn from your own Chess.com games: every move graded by Stockfish and explained in French or English.
Design: https://claude.ai/artifact/CxdoNZcFvBPCmpGE58shQv · Build plan: `docs/superpowers/plans/`.

## Run locally (Docker)

```bash
cp .env.example .env        # set DJANGO_SECRET_KEY, POSTGRES_PASSWORD, GEMINI_API_KEY
docker compose up --build
```

Open http://localhost:8000.

## Run tests (without Docker)

Needs Postgres (user/db `chess`, password `chess` on localhost), Stockfish at `/usr/games/stockfish`
(`apt install stockfish`), and Python 3.12+.

```bash
pip install -r requirements.txt
pytest
```

Tests use engine depth 8, no AI calls, and run Celery tasks inline (see `conftest.py`).

## Gemini (free tier)

Create a key in Google AI Studio and put it in `GEMINI_API_KEY`. Ordinary moves never call the AI.
Key moments (inaccuracies, mistakes, blunders) do. When the daily quota is used up, those moves get a
template sentence and are upgraded by a daily job at 08:05 UTC (`analysis.tasks.upgrade_pending_explanations`).
Check your model's free quota on the AI Studio rate-limit page and set `LIMIT_REVIEWS_PER_WEEK` from it.
Set `AI_PROVIDER=none` to run with templates only.

## Deploy on Oracle Cloud Always Free

1. Create one Ampere A1 (ARM) instance. Keep the total of all A1 instances at or under **2 OCPU / 12 GB**
   (the free limit since June 2026); going over gets A1 instances disabled.
2. Install Docker and the compose plugin, clone this repo, create `.env`, run `docker compose up -d --build`.
3. Put a reverse proxy with HTTPS in front of port 8000 (Caddy is the simplest), and set
   `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Licenses

- Stockfish is GPL-3.0 (https://github.com/official-stockfish/Stockfish). It runs as a separate process;
  the app talks to it over UCI.
- cm-chessboard (MIT) and chess.js (BSD-2-Clause) are bundled in `static/vendor/` with their license files.
