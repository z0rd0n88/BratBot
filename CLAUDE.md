# BratBot

Discord bot with a bratty, condescending personality, powered by a self-hosted LLM via Ollama.

## Architecture

- `src/bratbot/` — Discord bot (discord.py), async throughout
- `model/` — FastAPI personality API (talks to Ollama for LLM inference)
- Docker Compose stack: app + Ollama + Redis

## Dev Commands

- `uv sync --all-extras` — install all dependencies including dev
- `uv run pytest tests/ -v` — run tests
- `uv run ruff check src/ model/` — lint
- `uv run ruff format src/ model/` — format
- `docker compose up` — run full stack

## Conventions

- Python 3.12, Ruff for linting and formatting (line-length 100)
- Ruff rules: E, F, I, UP, B, SIM
- Async everywhere (pytest-asyncio with auto mode)
- pydantic-settings for configuration, structlog for structured logging
- httpx for HTTP clients (async)
- Do not edit `.env` files or `uv.lock` directly
