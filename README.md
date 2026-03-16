# Brat Bot

A Discord bot that answers questions with configurable levels of attitude. Brat Bot is performatively sassy: always helpful, never without drama. It answers your questions, roasts your phrasing, and makes sure you know it's doing you a favor.

Powered by a self-hosted LLM (via Ollama) with a custom personality API layer.

---

## Architecture

```
┌───────────────────────────────────────────────┐
│         app container (single image)          │
│                                               │
│  ┌───────────┐       ┌──────────────────┐     │
│  │  BratBot  │──────►│  BratBotModel    │     │
│  │  discord  │ :8000 │  FastAPI + brat   │     │
│  │  .py bot  │       │  personality      │     │
│  └───────────┘       └────────┬─────────┘     │
│                               │               │
└───────────────────────────────┼───────────────┘
                                │ :11434
                    ┌───────────▼───────────┐
                    │       Ollama          │
                    │   LLM inference       │
                    │   (GPU accelerated)   │
                    └───────────────────────┘

┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │    Redis     │
│    :5432     │    │    :6379     │
│  persistence │    │ rate limits  │
└──────────────┘    └──────────────┘
```

**Data flow:** Discord message → BratBot → `POST localhost:8000/chat` → BratBotModel → Ollama `/api/chat` → LLM inference → bratty reply → Discord

BratBot and BratBotModel run in the same container (managed by supervisord) and communicate via `localhost:8000`. Ollama runs as a separate GPU-enabled service. PostgreSQL and Redis provide persistence and rate limiting.

---

## Features

- **Self-Hosted LLM** — Runs on your own hardware via Ollama. No API keys, no usage fees, full control.
- **`/brat` Slash Command** — Ask a question with an optional brat level (1–5).
- **@Mention Support** — Mention the bot in any channel for free-form conversation.
- **Adjustable Brattiness** — 5 levels from mildly tedious to maximum diva.
- **Custom GGUF Models** — Import your own quantized model files via Modelfile, or pull from Ollama's registry.
- **Rate Limiting** — Per-user cooldowns and per-channel rate limits via Redis.
- **Request Queue** — Per-channel async queue prevents overlapping LLM responses.
- **Structured Logging** — JSON logs in production, colored console in development.
- **Global Error Handling** — In-character error messages for every failure mode.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Discord | discord.py 2.x |
| LLM Engine | Ollama (self-hosted) |
| Personality API | FastAPI (BratBotModel) |
| HTTP Client | httpx |
| Database | PostgreSQL 16 (SQLAlchemy async + asyncpg) |
| Migrations | Alembic |
| Cache | Redis 7 (async) |
| Config | pydantic-settings |
| Logging | structlog |
| Linting | ruff |
| Package Manager | uv |
| Containerization | Docker + docker-compose |
| Process Manager | supervisord |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (for GPU-accelerated inference)
- A [Discord bot token](https://discord.com/developers/applications)
- A GPU with enough VRAM for your chosen model

---

## Quick Start

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd BratBot
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
# Required
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_CLIENT_ID=your-discord-client-id
LLM_API_URL=http://localhost:8000

# Database (default matches docker-compose)
DATABASE_URL=postgresql+asyncpg://bratbot:bratbot@db:5432/bratbot

# Redis (default matches docker-compose)
REDIS_URL=redis://redis:6379/0
```

> **Note:** `LLM_API_URL` is `http://localhost:8000` because BratBot and BratBotModel run in the same container. When running via Docker Compose, use `db` and `redis` as hostnames (service names).

### 2. Set up the LLM model

You have two options:

**Option A: Pull from Ollama's registry (easiest)**

```bash
docker compose up --build -d
docker compose exec ollama ollama pull qwen3:14b
```

**Option B: Import a local GGUF file**

If you have a quantized GGUF model file (e.g., from Hugging Face), you can import it into Ollama using the included `Modelfile`.

1. Set the `LLM_MODELS_DIR` variable in `.env` to the directory containing your GGUF file:

   ```env
   LLM_MODELS_DIR=C:/Users/you/models
   ```

2. Edit the `Modelfile` to point to your model file. The path must use the container mount point (`/models/`):

   ```dockerfile
   FROM /models/Your-Model-File.gguf
   ```

3. Start the services and create the model in Ollama:

   ```bash
   docker compose up --build -d
   docker compose exec ollama ollama create qwen3-14b -f /models/Modelfile
   ```

4. Ensure `OLLAMA_MODEL` in `.env` matches the name you used in `ollama create`:

   ```env
   OLLAMA_MODEL=qwen3-14b
   ```

> **Tip:** The `Modelfile` is mounted into the Ollama container at `/models/Modelfile` via the `LLM_MODELS_DIR` volume. Store it alongside your GGUF files, or keep it in the repo root (it's copied during build).

### 3. Start all services

```bash
docker compose up --build
```

### 4. Verify

- The bot should appear online in your Discord server.
- Run `/ping` — responds with "Pong" and WebSocket latency.
- Run `/brat How do loops work?` — responds with a bratty explanation.
- @mention the bot — responds via the LLM pipeline.

---

## Services

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `app` | Built from Dockerfile | 8000 (internal) | BratBot + BratBotModel |
| `ollama` | `ollama/ollama` | 11434 | LLM inference (GPU) |
| `db` | `postgres:16-alpine` | 5432 | Persistent storage |
| `redis` | `redis:7-alpine` | 6379 | Rate limits, caching |

---

## Development Setup

### Local development (without Docker)

```bash
# Install dependencies
uv sync --extra dev

# Run the bot (requires PostgreSQL, Redis, and Ollama running locally)
uv run python -m bratbot
```

### Development with Docker (hot reload)

```bash
docker compose up --build
```

The `docker-compose.override.yml` provides:
- Source code mounted as read-only volumes
- Hot reload via `watchfiles`
- `LOG_LEVEL=DEBUG` for colored console output

### Linting

```bash
uv run ruff check src/
uv run ruff format src/
```

### Testing

```bash
uv run pytest -v            # Run all tests
```

Tests use `httpx.MockTransport` to mock the LLM server — no running services required.

---

## Project Structure

```
BratBot/
  pyproject.toml              # Dependencies and tool config
  Dockerfile                  # Combined BratBot + BratBotModel image
  docker-compose.yml          # All services (app, ollama, db, redis)
  docker-compose.override.yml # Dev overrides (hot reload, debug logging)
  supervisord.conf            # Process manager for combined container
  Modelfile                   # Ollama model import definition (for GGUF files)
  .env.example                # Environment variable template
  alembic.ini                 # Migration config
  alembic/
    env.py                    # Async migration environment
  model/
    app.py                    # BratBotModel FastAPI app (personality API)
    requirements.txt          # Model API dependencies
  src/
    bratbot/
      __main__.py             # Entry point
      bot.py                  # BratBot class — lifecycle, extensions, services
      config/
        settings.py           # pydantic-settings (env var validation)
      commands/
        ping.py               # /ping slash command
        brat.py               # /brat slash command (LLM query)
      events/
        ready.py              # on_ready listener
        guild.py              # Guild join/remove logging
        messages.py           # @mention → LLM pipeline
        errors.py             # Global error handler
      services/
        llm_client.py         # Async HTTP client for BratBotModel API
        rate_limiter.py       # Redis rate limiting
        request_queue.py      # Per-channel async LLM queue
      models/
        base.py               # SQLAlchemy async engine + session factory
      utils/
        logger.py             # structlog setup
        redis.py              # Async Redis client singleton
  tests/
    conftest.py               # Shared fixtures
    test_llm_client.py        # 24 tests for LLM client
```

---

## Brat Levels

| Level | Personality | Example |
|---|---|---|
| 1 | Mildly tedious | *sigh* A loop iterates over a sequence... |
| 2 | Dry sarcasm | Oh, you mean what every tutorial covers? Sure... |
| 3 | Snarky & impatient | Let me take time out of my *busy* schedule... |
| 4 | Condescending | Must I do ALL the thinking around here? |
| 5 | Maximum brat | The AUDACITY of this question. The sheer NERVE... |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | — | Bot token from Discord Developer Portal |
| `DISCORD_CLIENT_ID` | Yes | — | Application ID from Discord Developer Portal |
| `LLM_API_URL` | Yes | — | BratBotModel URL (`http://localhost:8000` in Docker) |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `REDIS_URL` | Yes | — | Redis connection string |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `GUILD_ID` | No | — | Dev guild ID for instant slash command sync |
| `LLM_BRAT_LEVEL` | No | `3` | Default brat level (1–5) |
| `RATE_LIMIT_USER_SECONDS` | No | `5` | Per-user cooldown in seconds |
| `RATE_LIMIT_CHANNEL_PER_MINUTE` | No | `10` | Max requests per channel per minute |
| `LLM_QUEUE_MAX_DEPTH` | No | `5` | Max queued LLM requests per channel |
| `LLM_TIMEOUT_SECONDS` | No | `30` | LLM request timeout in seconds |
| `OLLAMA_BASE_URL` | No | `http://ollama:11434` | Ollama API URL (used by BratBotModel) |
| `OLLAMA_MODEL` | No | `qwen3-14b` | Ollama model name |
| `LLM_MODELS_DIR` | No | — | Host path to GGUF model files (mounted into Ollama at `/models`) |

---

## Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, click "Add Bot" and copy the token → `DISCORD_BOT_TOKEN`.
3. Copy the Application ID from **General Information** → `DISCORD_CLIENT_ID`.
4. Under **Bot**, enable **Message Content Intent** (required for @mention support).
5. Generate an invite URL under **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`
6. Invite the bot to your server.

---

## Command Reference

| Command | Description |
|---|---|
| `/ping` | Check if the bot is alive (returns latency) |
| `/brat <message> [brat_level]` | Ask a question with optional attitude level (1–5) |

You can also @mention the bot in any channel for conversational responses (uses the default brat level).

---

## Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "describe changes"

# Apply migrations
uv run alembic upgrade head

# Inside Docker
docker compose exec app alembic upgrade head
```

---

## Troubleshooting

**Bot is online but `/brat` doesn't appear**
Slash commands take up to an hour to sync globally. Set `GUILD_ID` in `.env` for instant sync during development.

**"LLM server unhealthy" on startup**
The bot starts before Ollama finishes loading the model. This is normal — the health check logs a warning, and requests will succeed once Ollama is ready.

**Slow first response**
Ollama loads the model into VRAM on the first request. Use `/ping` first, then check `docker compose exec ollama ollama list` to confirm the model is loaded.

**Out of VRAM**
Try a smaller model or more aggressive quantization (e.g., `qwen3:8b` instead of `qwen3:14b`).

**"Model not found" in health check**
Ensure the model name in `OLLAMA_MODEL` matches what's in Ollama. Run `docker compose exec ollama ollama list` to see available models.

---

## License

This project is unlicensed. Add a `LICENSE` file to specify terms.
