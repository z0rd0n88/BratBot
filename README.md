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
                               │ conv history │
                               └──────────────┘
```

**Data flow:** Discord message → Bot → `POST localhost:8000/<personality>` → BratBotModel → Ollama `/api/chat` → LLM reply → Discord

Each bot has its own personality endpoint (`/bratchat`, `/bonniebot`) with isolated system prompts. Both bots share the same model server, Ollama instance, and Redis. All services run in the same container (managed by supervisord).

---

## Features

- **Multi-Personality Monorepo** — Multiple Discord bots sharing one codebase. Bug fixes apply to all bots automatically.
- **Self-Hosted LLM** — Runs on your own hardware via Ollama. No API keys, no usage fees, full control.
- **Slash Commands** — `/bratchat`, `/camichat` (BratBot), `/bonniebot` (BonnieBot), plus shared commands (`/ping`, `/intensity`, `/verbose`, `/help`, `/forget`, `/forgetall`).
- **@Mention Support** — Mention either bot in any channel for free-form conversation.
- **Conversation History** — Per-user, per-channel, per-persona sliding window of the last N exchanges (default 10), injected as proper multi-turn messages into every LLM request. Users can clear history with `/forget` or `/forgetall`.
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

# Personality prompts encryption key (see Personality Prompts section below)
PROMPTS_ENCRYPTION_KEY=your-base64-key-here
```

> **Note:** `LLM_API_URL` is `http://localhost:8000` because BratBot and BratBotModel run in the same container. When running via Docker Compose, use `redis` as the hostname (service name).

> **Personality prompts:** The model server expects a `PROMPTS_ENCRYPTION_KEY` to decrypt the committed `model/prompts/*.txt.enc` files at startup. See [Personality Prompts](#personality-prompts) below for the keygen + encrypt workflow before running the bot.

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
- Run `/camichat What's a closure?` — Cami responds with her own personality.
- Run `/bonniebot Hello!` — BonnieBot responds with its own personality.
- @mention either bot — responds via the LLM pipeline.

---

## Personality Prompts

Each personality (BratBot level 3, Cami, Bonnie) has its full system prompt
defined in a `model/prompts/*.txt` file. These contain custom voice content
that's not appropriate for public git history, so the plaintext files are
**gitignored**. To make the prompts survive a fresh clone or pod rebuild
without exposing them, the repo commits **encrypted** `*.txt.enc` files
(base64-encoded PyNaCl SecretBox ciphertext). The model server decrypts
them at startup using `PROMPTS_ENCRYPTION_KEY` from the environment.

### First-time setup

1. **Generate an encryption key** (one-time, store it safely):

   ```bash
   python scripts/encrypt-prompts.py keygen
   ```

   Add the printed key to your local `.env` as `PROMPTS_ENCRYPTION_KEY=...`
   **and** to the same env var in your RunPod pod template. Save it in a
   password manager — losing this key means losing access to the committed
   ciphertext.

2. **Create your local plaintext prompts** by copying the skeletons:

   ```bash
   cp model/prompts/brat_level3.txt.example model/prompts/brat_level3.txt
   cp model/prompts/cami.txt.example       model/prompts/cami.txt
   cp model/prompts/bonnie.txt.example     model/prompts/bonnie.txt
   ```

   Then edit each `.txt` file with your custom personality voice content.

3. **Encrypt the plaintext into committed `.txt.enc` files**:

   ```bash
   python scripts/encrypt-prompts.py encrypt
   ```

   This produces `model/prompts/{brat_level3,cami,bonnie}.txt.enc`. Commit
   the `.txt.enc` files (NOT the `.txt` files — they're gitignored).

### Editing prompts

```bash
# 1. Edit the plaintext (gitignored, local only)
$EDITOR model/prompts/bonnie.txt

# 2. Re-encrypt into the committed .txt.enc
python scripts/encrypt-prompts.py encrypt

# 3. Commit and push the updated .enc file
git add model/prompts/bonnie.txt.enc
git commit -m "tweak bonnie's voice"
git push

# 4. Either rebuild the image or hot-fix the running pod
```

The `encrypt` subcommand is **idempotent**: running it without changing
any plaintext is a no-op (the ciphertext doesn't change because the
existing file already decrypts to the same content).

### Fresh-clone recovery

After cloning the repo on a new machine:

```bash
cp .env.example .env
$EDITOR .env  # paste PROMPTS_ENCRYPTION_KEY from your password manager

# Materialize plaintext .txt files for editing (optional)
python scripts/encrypt-prompts.py decrypt
```

You don't actually need to run `decrypt` to start the bot — the model
server will decrypt the committed `.txt.enc` files at boot directly into
memory. Only run `decrypt` if you want to edit the plaintext locally.

### Optional: drift-check pre-commit hook

To prevent accidentally committing a stale `.txt.enc` after editing the
plaintext, install the optional pre-commit hook:

```bash
cp scripts/pre-commit-encrypt-check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook calls `scripts/encrypt-prompts.py verify` on every staged
`.txt.enc` file and aborts the commit if it doesn't match its sibling
`.txt` working copy. Requires `PROMPTS_ENCRYPTION_KEY` in your shell env.

The same drift check also runs in `./scripts/deploy-runpod.sh build` so
the build aborts before producing an image with stale prompts.

---

## Services

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `app` | Built from Dockerfile | 8000 | BratBot (Discord) + BratBotModel |
| `bonniebot` | Built from Dockerfile | — | BonnieBot (Discord) — shares model server via `app` |
| `ollama` | `ollama/ollama` | 11434 | LLM inference (GPU) |
| `redis` | `redis:7-alpine` | 6379 | Rate limits, user preferences, conversation history |

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
        cami.py               # /camichat (Cami personality, LLM query)
        intensity.py          # /intensity (1-3 attitude level)
        verbose.py            # /verbose (1-3 response length)
        help.py               # /help (list available commands)
        forget.py             # /forget (persona-specific), /forgetall
      events/                 # Shared event handlers (used by all bots)
        ready.py              # on_ready listener
        guild.py              # Guild join/remove logging
        messages.py           # @mention → LLM pipeline (fetches/stores history)
        errors.py             # Global error handler
      services/               # Shared services (used by all bots)
        llm_client.py         # Async HTTP client for personality API
        rate_limiter.py       # Redis rate limiting
        request_queue.py      # Per-channel async LLM queue
        intensity_store.py    # Per-user intensity preference (Redis)
        verbosity_store.py    # Per-user verbosity preference (Redis)
        conversation_history.py  # Per-user/channel/persona history (Redis)
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
        help.py               # /help (list available commands)
        forget.py             # /forget, /forgetall
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
| `HISTORY_SIZE` | No | `10` | Number of past exchanges to include in each LLM request |
| `OLLAMA_BASE_URL` | No | `http://ollama:11434` | Ollama API URL (used by BratBotModel) |
| `OLLAMA_MODEL` | No | `mannix/llama3.1-8b-abliterated:q8_0` | Ollama model name |
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
| `BONNIEBOT_HISTORY_SIZE` | No | `10` | Number of past exchanges to include in each LLM request |

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
| `/camichat <message>` | Ask Cami a question |
| `/intensity [1-3]` | Set or view your preferred brat intensity (1=mild, 2=medium, 3=maximum) |
| `/verbose [1-3]` | Set or view your preferred response length (1=short, 2=medium, 3=long) |
| `/forget <persona>` | Clear your conversation history for `bratbot` or `cami` in this channel |
| `/forgetall` | Clear your conversation history for all personas in this channel |

### BonnieBot Commands

| Command | Description |
|---|---|
| `/ping` | Check if the bot is alive (returns latency) |
| `/bonniebot <message>` | Talk to Bonnie |
| `/intensity [1-3]` | Set or view your preferred intensity |
| `/verbose [1-3]` | Set or view your preferred response length |
| `/forget` | Clear your BonnieBot conversation history in this channel |
| `/forgetall` | Clear your conversation history for all personas in this channel |

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

---

## License

This project is unlicensed. Add a `LICENSE` file to specify terms.
