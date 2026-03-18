# BratBot

Discord bot with a bratty, condescending personality, powered by a self-hosted LLM via Ollama.

## Architecture

- `src/bratbot/` — Discord bot (discord.py), async throughout
- `model/` — FastAPI personality API (talks to Ollama for LLM inference)
- Docker Compose stack: app + Ollama + Redis

## Environment

- `.env.example` — local dev template (DISCORD_BOT_TOKEN, DISCORD_CLIENT_ID, DISCORD_PUBLIC_KEY, LLM_API_URL, REDIS_URL required)
- `.env.runpod.example` — RunPod deploy template (adds RUNPOD_POD_ID, REGISTRY_IMAGE, RUNPOD_SSH_KEY)

## Dev Commands

- `uv sync --all-extras` — install all dependencies including dev
- `uv run pytest tests/ -v` — run tests
- `uv run ruff check src/ model/` — lint
- `uv run ruff format src/ model/` — format
- `docker compose up` — run full stack

## Deployment

- `./scripts/deploy-runpod.sh build` — build RunPod Docker image
- `./scripts/deploy-runpod.sh push` — push to GHCR
- `./scripts/deploy-runpod.sh update` — build + push + restart pod
- `./scripts/deploy-runpod.sh ssh` — SSH into RunPod pod
- `./scripts/deploy-runpod.sh status` — check supervisord status on pod
- `./scripts/deploy-runpod.sh logs` — tail logs on pod
- RunPod config lives in `.env.runpod` (see `.env.runpod.example`)
- Two Dockerfiles: `Dockerfile` (Compose, Ollama separate) / `Dockerfile.runpod` (all-in-one with Ollama)

## Conventions

- Python 3.12, Ruff for linting and formatting (line-length 100)
- Ruff rules: E, F, I, UP, B, SIM
- Async everywhere (pytest-asyncio with auto mode)
- pydantic-settings for configuration, structlog for structured logging
- httpx for HTTP clients (async)
- Do not edit `.env` files or `uv.lock` directly

## Gotchas

- Cogs auto-discovered via `pkgutil.iter_modules()` in `bot.py` — just add a file with `async def setup(bot)` to `commands/` or `events/`
- `model/` is not a Python package (no `__init__.py`) — tests add it to `sys.path` manually
- Rate limiter degrades gracefully: if Redis is down, requests are allowed through
- All Discord-facing error messages must stay in-character (bratty); never expose stack traces
- Discord message limit is 2000 chars — LLMClient truncates automatically
