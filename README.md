```
  ◆ ✦ ◆ ✦ ◆ ✦ ◆
    B R A T B O T
  ✦ ◆ ✦ ◆ ✦ ◆ ✦
```

# Brat Bot

A multi-personality Discord bot monorepo powered by a self-hosted LLM (via Ollama) with a custom personality API layer.

**BratBot** is performatively sassy: always helpful, never without drama. It answers your questions, roasts your phrasing, and makes sure you know it's doing you a favor.

**BonnieBot** is a second personality that runs as a separate Discord bot but shares the same infrastructure, services, and bug fixes.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│              app container (single image)                │
│                                                          │
│  ┌───────────┐                                           │
│  │  BratBot  │─── POST /bratchat ───────►┐              │
│  │  discord  │                           │              │
│  │  .py bot  │                           │              │
│  └───────────┘                           ▼              │
│                           ┌──────────────────────────────┐
│  ┌───────────┐            │       BratBotModel           │
│  │ BonnieBot │─── POST /bonniebot ──►    (FastAPI)       │
│  │  discord  │            │   personality endpoints      │
│  │  .py bot  │            └──────────────┬───────────────┘
│  └───────────┘                           │                │
│                                          │                │
└──────────────────────────────────────────┼──────────────┘
                                           │ :11434
                               ┌───────────▼───────────┐
                               │       Ollama          │
                               │   LLM inference       │
                               │   (GPU accelerated)   │
                               └───────────────────────┘

                               ┌──────────────┐
                               │    Redis     │
                               │    :6379     │
                               │ rate limits  │
                               └──────────────┘
```

**Data flow:** Discord message → Bot → `POST localhost:8000/<personality>` → BratBotModel → Ollama `/api/chat` → LLM reply → Discord

Each bot has its own personality endpoint (`/bratchat`, `/bonniebot`) with isolated system prompts. Both bots share the same model server, Ollama instance, and Redis. All services run in the same container (managed by supervisord).

---

## Features

- **Multi-Personality Monorepo** — Multiple Discord bots sharing one codebase. Bug fixes apply to all bots automatically.
- **Self-Hosted LLM** — Runs on your own hardware via Ollama. No API keys, no usage fees, full control.
- **Slash Commands** — `/bratchat` (BratBot), `/bonniebot` (BonnieBot), plus shared commands (`/ping`, `/intensity`, `/verbose`).
- **@Mention Support** — Mention either bot in any channel for free-form conversation.
- **Adjustable Intensity** — Per-user intensity levels (1–3) via the `/intensity` command.
- **Adjustable Verbosity** — Per-user response length (1–3) via the `/verbose` command.
- **Custom GGUF Models** — Import your own quantized model files via Modelfile, or pull from Ollama's registry.
- **Rate Limiting** — Per-user cooldowns and per-channel rate limits via Redis.
- **Request Queue** — Per-channel async queue prevents overlapping LLM responses.
- **Structured Logging** — JSON logs in production, colored console in development.
- **Global Error Handling** — In-character error messages for every failure mode, per personality.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Discord | discord.py 2.x |
| LLM Engine | Ollama (self-hosted) |
| Personality API | FastAPI (BratBotModel) |
| HTTP Client | httpx |
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

# Redis (default matches docker-compose)
REDIS_URL=redis://redis:6379/0
```

> **Note:** `LLM_API_URL` is `http://localhost:8000` because BratBot and BratBotModel run in the same container. When running via Docker Compose, use `redis` as the hostname (service name).

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

- Both bots should appear online in your Discord server.
- Run `/ping` on either bot — responds with "Pong" and WebSocket latency.
- Run `/bratchat How do loops work?` — BratBot responds with a bratty explanation.
- Run `/bonniebot Hello!` — BonnieBot responds with its own personality.
- @mention either bot — responds via the LLM pipeline.

---

## Deploying to RunPod

RunPod GPU Pods provide a persistent VM-like environment with dedicated GPU — ideal for running the bot 24/7 with Ollama inference.

### Architecture

The pod runs the bot, model API, and Ollama in a single stateless container. Redis is hosted externally (Upstash free tier) for rate limiting, so the pod can be stopped or replaced freely.

```
RunPod GPU Pod (stateless)
├── supervisord
│   ├── ollama serve          (GPU, port 11434)
│   ├── model (uvicorn)       (port 8000)
│   ├── bot (bratbot)         (outbound WebSocket)
│   └── bonniebot             (outbound WebSocket)
└── /workspace (Network Volume)
    ├── models/Qwen_Qwen3-14B-Q4_K_M.gguf
    └── ollama/

External Services:
└── Upstash Redis (free tier)
```

### GPU Recommendations

| GPU | VRAM | ~Cost/hr | ~Cost/mo | Notes |
|---|---|---|---|---|
| RTX A4000 | 16GB | $0.20 | $144 | Cheapest viable for 14B Q4_K_M |
| L4 | 24GB | $0.28 | $202 | Good balance of cost and headroom |
| RTX 4090 | 24GB | $0.44 | $317 | Fastest inference |

### Prerequisites

1. **Upstash Redis** — Create a free account at [upstash.com](https://upstash.com), create a Redis database. Note the `rediss://` connection string (TLS).
2. **RunPod account** with a container registry (Docker Hub or GHCR) for pushing images.

### Step 1: Build and push the RunPod image

```bash
# Configure your registry (one-time)
cp .env.runpod.example .env.runpod
# Edit .env.runpod with your REGISTRY_IMAGE and RUNPOD_POD_ID

# Build and push
./scripts/deploy-runpod.sh build
./scripts/deploy-runpod.sh push
```

### Step 2: Set up RunPod Network Volume

1. Create a **Network Volume** (15 GB) in your preferred RunPod region.
2. This volume stores the Ollama model cache at `/workspace/ollama/`. Models pulled from the Ollama registry are cached here automatically — no manual upload needed.
3. For custom GGUF files, spin up a temporary CPU pod and upload to `/workspace/models/`.

**Storage layout:**
```
Network Volume (/workspace):
├── ollama/models/          ← Ollama model cache (persistent across restarts)
└── models/                 ← Custom GGUF files (optional)
```

On first boot, the entrypoint pulls the model specified by `OLLAMA_MODEL` (~2–10 min depending on size). Subsequent restarts load from cache in ~30 seconds.

### Step 3: Create Pod Template

In the RunPod console, create a Pod Template:

- **Image:** `ghcr.io/<your-org>/bratbot:runpod-latest`
- **GPU:** RTX 3070 for small models, RTX A4000 for 14B (see table below)
- **Container Disk:** 5 GB (models live on network volume, container image is ~900 MB)
- **Volume:** Attach your network volume at `/workspace`
- **Exposed Ports:** `8000/http` (Discord interactions webhook)
- **Environment Variables:**

| Variable | Value |
|---|---|
| `DISCORD_BOT_TOKEN` | Your Discord bot token |
| `DISCORD_CLIENT_ID` | Your Discord client ID |
| `DISCORD_PUBLIC_KEY` | Your Discord public key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `qwen3:8b` (or any model from the table below) |
| `LLM_API_URL` | `http://localhost:8000` |
| `REDIS_URL` | `rediss://default:xxx@xxx.upstash.io:6379` |

### Step 4: Deploy and verify

```bash
# Check everything is running
./scripts/deploy-runpod.sh status

# Or SSH in manually
./scripts/deploy-runpod.sh ssh
```

### Verify deployment

```bash
# Check all services are running
./scripts/deploy-runpod.sh status

# Verify model is loaded
./scripts/deploy-runpod.sh ssh
ollama list
curl http://localhost:8000/health
```

### Switching models

Switch models on a running pod without rebuilding or restarting the pod:

```bash
# See available models and recommendations
./scripts/deploy-runpod.sh switch-model

# Pull a new model from the Ollama registry and activate it
./scripts/deploy-runpod.sh switch-model qwen3:8b

# Or import a custom GGUF from the network volume
./scripts/deploy-runpod.sh switch-model my-model --gguf /workspace/models/my-model.gguf

# Check what's loaded
./scripts/deploy-runpod.sh models
```

> **Note:** `switch-model` activates the model immediately but doesn't persist across pod restarts. Update `OLLAMA_MODEL` in your pod template to make it permanent.

### Recommended models by cost

| Model | VRAM | Quality | Min GPU | ~Cost/mo |
|---|---|---|---|---|
| `llama3.2:3b` | ~2 GB | Decent | RTX 3070 | ~$72 |
| `qwen3:4b` | ~3 GB | Good | RTX 3070 | ~$72 |
| `phi4-mini` | ~3 GB | Good | RTX 3070 | ~$72 |
| `gemma3:4b` | ~3 GB | Good | RTX 3070 | ~$72 |
| `qwen3:8b` | ~5 GB | Great | RTX 3070 | ~$72 |
| `gemma3:12b` | ~8 GB | Excellent | RTX A4000 | ~$144 |
| `qwen3:14b` | ~9 GB | Excellent | RTX A4000 | ~$144 |

> **Tip:** Start with `qwen3:8b` on an RTX 3070 (~$72/mo) for the best balance of quality and cost. The bot's personality comes from the system prompt, so even smaller models produce entertaining bratty responses.

### Updating code

For pure code changes (no new dependencies), use `hot-update` — it syncs source files
over SCP and restarts only the Python services. Ollama stays running with the model
loaded in VRAM, so there's no model reload delay:

```bash
./scripts/deploy-runpod.sh hot-update
```

For changes that add or remove Python dependencies (i.e., `pyproject.toml` or
`model/requirements.txt` changed), do a full deploy:

```bash
./scripts/deploy-runpod.sh update
```

### Deploy script reference

```bash
./scripts/deploy-runpod.sh build           # Build Docker image
./scripts/deploy-runpod.sh push            # Push to registry
./scripts/deploy-runpod.sh hot-update      # Sync code + restart (Ollama stays up)
./scripts/deploy-runpod.sh update          # Build + push + restart (full deploy)
./scripts/deploy-runpod.sh switch-model    # Change active model
./scripts/deploy-runpod.sh status          # Check services + health
./scripts/deploy-runpod.sh ssh             # SSH into the pod
./scripts/deploy-runpod.sh logs [service]  # Tail logs
./scripts/deploy-runpod.sh models          # List loaded models
```

---

## Services

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `app` | Built from Dockerfile | 8000 | BratBot (Discord) + BratBotModel |
| `bonniebot` | Built from Dockerfile | — | BonnieBot (Discord) — shares model server via `app` |
| `ollama` | `ollama/ollama` | 11434 | LLM inference (GPU) |
| `redis` | `redis:7-alpine` | 6379 | Rate limits |

---

## Development Setup

### Local development (without Docker)

```bash
# Install dependencies
uv sync --extra dev

# Run BratBot (requires Redis and Ollama running locally)
uv run python -m bratbot

# Run BonnieBot (separate terminal, requires BONNIEBOT_* env vars)
uv run python -m bonniebot
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
  Dockerfile                  # Combined BratBot + BratBotModel image (local)
  Dockerfile.runpod           # RunPod image (includes Ollama)
  docker-compose.yml          # All services (app, bonniebot, ollama, redis)
  docker-compose.override.yml # Dev overrides (hot reload, debug logging)
  supervisord.conf            # Process manager for local container
  supervisord.runpod.conf     # Process manager for RunPod (ollama + model + bots)
  Modelfile                   # Ollama model import definition (for GGUF files)
  .env.example                # Environment variable template (local)
  .env.runpod.example         # RunPod deployment config template
  scripts/
    deploy-runpod.sh          # Build, push, switch models, manage pod
    runpod-entrypoint.sh      # RunPod container startup script
  model/
    app.py                    # BratBotModel FastAPI app (personality endpoints)
    prompts/                  # System prompt files per personality
    requirements.txt          # Model API dependencies
  src/
    bratbot/                  # BratBot + shared infrastructure
      __main__.py             # Entry point (python -m bratbot)
      bot.py                  # BratBot class — lifecycle, extensions, services
      personality.py          # Personality dataclass + BRAT_PERSONALITY
      config/
        settings.py           # pydantic-settings (env var validation)
      commands/               # BratBot-specific slash commands
        ping.py               # /ping
        bratchat.py           # /bratchat (LLM query)
        intensity.py          # /intensity (1-3 attitude level)
        verbose.py            # /verbose (1-3 response length)
      events/                 # Shared event handlers (used by all bots)
        ready.py              # on_ready listener
        guild.py              # Guild join/remove logging
        messages.py           # @mention → LLM pipeline
        errors.py             # Global error handler
      services/               # Shared services (used by all bots)
        llm_client.py         # Async HTTP client for personality API
        rate_limiter.py       # Redis rate limiting
        request_queue.py      # Per-channel async LLM queue
        intensity_store.py    # Per-user intensity preference (Redis)
        verbosity_store.py    # Per-user verbosity preference (Redis)
      utils/
        logger.py             # structlog setup
        redis.py              # Async Redis client singleton
    bonniebot/                # BonnieBot personality (thin wrapper)
      __main__.py             # Entry point (python -m bonniebot)
      bot.py                  # BonnieBot class — loads bratbot.events
      personality.py          # BONNIE_PERSONALITY strings
      config/
        settings.py           # BONNIEBOT_* env vars
      commands/               # BonnieBot-specific slash commands
        bonniebot.py          # /bonniebot (LLM query)
        ping.py               # /ping
        intensity.py          # /intensity
        verbose.py            # /verbose
  tests/
    conftest.py               # Shared fixtures
    test_llm_client.py        # LLM client tests
    test_messages_handler.py  # Message dedup tests
```

---

## Personality System

The monorepo supports multiple bot personalities sharing one codebase. Each personality is a thin wrapper that defines:

1. **Response strings** — rate-limit messages, error messages, empty-mention replies (all in-character)
2. **LLM system prompt** — the personality file in `model/prompts/` that defines how the bot talks
3. **Chat endpoint** — each bot calls its own model server endpoint (`/bratchat`, `/bonniebot`)
4. **Slash commands** — each bot has its own command names (`/bratchat`, `/bonniebot`)

Shared infrastructure (event handlers, services, rate limiting, dedup) lives in `bratbot.events` and `bratbot.services`. BonnieBot loads `bratbot.events` as its event source, so bug fixes to message handling, error routing, and rate limiting automatically apply to both bots.

### Adding a new personality

1. Create `src/<botname>/` mirroring `src/bonniebot/` structure
2. Define a `Personality` instance with your bot's strings and endpoint
3. Set `_COG_PACKAGES = ("bratbot.events", "<botname>.commands")` in your bot class
4. Add a new endpoint in `model/app.py` and a system prompt in `model/prompts/`
5. Add env vars, docker-compose service, and supervisord program

## Brat Levels

| Level | Personality | Example |
|---|---|---|
| 1 | Mildly tedious | *sigh* A loop iterates over a sequence... |
| 2 | Dry sarcasm | Oh, you mean what every tutorial covers? Sure... |
| 3 | Maximum brat | The AUDACITY of this question. The sheer NERVE... |

---

## LLM Inference Parameters

BratBotModel passes these options to Ollama on every inference request. All three are configurable via environment variables — set them in `.env` or your pod template.

| Parameter | Env Var | Default | Description |
|---|---|---|---|
| `num_ctx` | `OLLAMA_NUM_CTX` | `32768` | **Context window size** — total token budget for input + output combined. The system prompt, user message, and generated reply all count against this limit. 32K fits comfortably on an RTX 4090 with an 8B Q4 model (~10GB KV cache). Reduce to `8192` for GPUs with less VRAM. |
| `num_predict` | `OLLAMA_NUM_PREDICT` | `-1` | **Max output tokens** — caps how many tokens the model generates per response. `-1` means unlimited: the model stops at its natural end-of-sequence token. In practice, Discord's 2000-character limit (~500 tokens) is the real hard cap for Discord responses. |
| `temperature` | `OLLAMA_TEMPERATURE` | `0.9` | **Sampling randomness** — controls creativity vs. determinism. `0.0` always picks the highest-probability token (robotic, repetitive). `1.0` is highly random. `0.9` keeps responses lively and spontaneous, which suits the bratty personality. |

To override any of these, set the corresponding variable in `.env`:

```env
OLLAMA_TEMPERATURE=0.9
OLLAMA_NUM_PREDICT=-1
OLLAMA_NUM_CTX=32768
```

---

## Environment Variables

### BratBot (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | — | Bot token from Discord Developer Portal |
| `DISCORD_CLIENT_ID` | Yes | — | Application ID from Discord Developer Portal |
| `DISCORD_PUBLIC_KEY` | Yes | — | Ed25519 key for interaction signature verification |
| `LLM_API_URL` | Yes | — | BratBotModel URL (`http://localhost:8000` in Docker) |
| `REDIS_URL` | Yes | — | Redis connection string |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `GUILD_ID` | No | — | Dev guild ID for instant slash command sync |
| `LLM_BRAT_LEVEL` | No | `3` | Default brat level (1–3, where 3 is maximum) |
| `RATE_LIMIT_USER_SECONDS` | No | `5` | Per-user cooldown in seconds |
| `RATE_LIMIT_CHANNEL_PER_MINUTE` | No | `10` | Max requests per channel per minute |
| `LLM_QUEUE_MAX_DEPTH` | No | `5` | Max queued LLM requests per channel |
| `LLM_TIMEOUT_SECONDS` | No | `30` | LLM request timeout in seconds |
| `OLLAMA_BASE_URL` | No | `http://ollama:11434` | Ollama API URL (used by BratBotModel) |
| `OLLAMA_MODEL` | No | `qwen3-14b` | Ollama model name |
| `LLM_MODELS_DIR` | No | — | Host path to GGUF model files (mounted into Ollama at `/models`) |

### BonnieBot (`.env`)

BonnieBot uses the `BONNIEBOT_` prefix for all settings. Only Discord credentials differ; `LLM_API_URL` and `REDIS_URL` point to the same shared services.

| Variable | Required | Default | Description |
|---|---|---|---|
| `BONNIEBOT_DISCORD_BOT_TOKEN` | Yes | — | BonnieBot token (separate Discord application) |
| `BONNIEBOT_DISCORD_CLIENT_ID` | Yes | — | BonnieBot application ID |
| `BONNIEBOT_DISCORD_PUBLIC_KEY` | Yes | — | BonnieBot Ed25519 key |
| `BONNIEBOT_LLM_API_URL` | Yes | — | Same model server as BratBot |
| `BONNIEBOT_REDIS_URL` | Yes | — | Same Redis as BratBot |

---

## Discord Bot Setup

Each personality requires its own Discord application. Repeat these steps for both BratBot and BonnieBot:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, click "Add Bot" and copy the token → `DISCORD_BOT_TOKEN` (or `BONNIEBOT_DISCORD_BOT_TOKEN`).
3. Copy the Application ID from **General Information** → `DISCORD_CLIENT_ID` (or `BONNIEBOT_DISCORD_CLIENT_ID`).
4. Copy the Public Key from **General Information** → `DISCORD_PUBLIC_KEY` (or `BONNIEBOT_DISCORD_PUBLIC_KEY`).
5. Under **Bot**, enable **Message Content Intent** (required for @mention support).
6. Generate an invite URL under **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`
7. Invite the bot to your server.

---

## Command Reference

### BratBot Commands

| Command | Description |
|---|---|
| `/ping` | Check if the bot is alive (returns latency) |
| `/bratchat <message>` | Ask BratBot a question |
| `/intensity [1-3]` | Set or view your preferred brat intensity (1=mild, 2=medium, 3=maximum) |
| `/verbose [1-3]` | Set or view your preferred response length (1=short, 2=medium, 3=long) |

### BonnieBot Commands

| Command | Description |
|---|---|
| `/ping` | Check if the bot is alive (returns latency) |
| `/bonniebot <message>` | Talk to Bonnie |
| `/intensity [1-3]` | Set or view your preferred intensity |
| `/verbose [1-3]` | Set or view your preferred response length |

You can also @mention either bot in any channel for conversational responses.

---

## Troubleshooting

**Bot is online but `/bratchat` doesn't appear**
Slash commands take up to an hour to sync globally. Set `GUILD_ID` in `.env` for instant sync during development.

**"LLM server unhealthy" on startup**
The bot starts before Ollama finishes loading the model. This is normal — the health check logs a warning, and requests will succeed once Ollama is ready.

**Slow first response**
Ollama loads the model into VRAM on the first request. Use `/ping` first, then check `docker compose exec ollama ollama list` to confirm the model is loaded.

**Out of VRAM**
Try a smaller model or more aggressive quantization (e.g., `qwen3:8b` instead of `qwen3:14b`).

**"Model not found" in health check**
Ensure the model name in `OLLAMA_MODEL` matches what's in Ollama. Run `docker compose exec ollama ollama list` to see available models.

**Models not persisting after RunPod pod restart**
Verify the network volume is attached at `/workspace`: `df /workspace`. If empty, the volume wasn't mounted — recreate the pod with the volume properly attached. Model files should exist at `/workspace/ollama/models/`.

---

## License

This project is unlicensed. Add a `LICENSE` file to specify terms.
