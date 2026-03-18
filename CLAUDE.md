# BratBot

Discord bot with a bratty, condescending personality, powered by a self-hosted LLM via Ollama.

## Architecture

- `src/bratbot/` — Discord bot (discord.py), async throughout
- `model/` — FastAPI personality API (talks to Ollama for LLM inference)
- `alembic/` — Database migrations (PostgreSQL)
- Docker Compose stack: app + Ollama + Postgres + Redis

## Dev Commands

- `uv sync --all-extras` — install all dependencies including dev
- `uv run pytest tests/ -v` — run tests
- `uv run ruff check src/ model/` — lint
- `uv run ruff format src/ model/` — format
- `docker compose up` — run full stack
- `uv run alembic revision --autogenerate -m "description"` — create migration
- `uv run alembic upgrade head` — apply migrations

## Conventions

- Python 3.12, Ruff for linting and formatting (line-length 100)
- Ruff rules: E, F, I, UP, B, SIM
- Async everywhere (SQLAlchemy async sessions, pytest-asyncio with auto mode)
- pydantic-settings for configuration, structlog for structured logging
- httpx for HTTP clients (async)
- Do not edit `.env` files or `uv.lock` directly
