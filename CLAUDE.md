# BratBot

Discord bot with a bratty, condescending personality, powered by a self-hosted LLM via Ollama.

## Architecture

- `src/bratbot/` — Discord bot (discord.py), async throughout
- `src/bonniebot/` — Second bot personality, shares infrastructure with bratbot via common
- `src/common/` — Shared package: Personality dataclass, event cogs, services, utils
- `model/` — FastAPI personality API (talks to Ollama for LLM inference)
- Docker Compose stack: app + Ollama + Redis

## Environment

- `.env.example` — local dev template (DISCORD_BOT_TOKEN, DISCORD_CLIENT_ID, DISCORD_PUBLIC_KEY, LLM_API_URL, REDIS_URL required)
- `.env.runpod.example` — RunPod deploy template (adds RUNPOD_POD_ID, REGISTRY_IMAGE, RUNPOD_SSH_KEY)

## Dev Commands

- **`uv` not on PATH**: use `.venv/Scripts/python.exe -m <tool>` for pytest, ruff, etc. (or `uv run` if `uv` is available)
- **`jq` not on PATH**: shell hooks and scripts that parse JSON must use `python -c "import sys,json; ..."` — bare `jq` fails silently
- **Pre-commit hook on Windows**: the encrypt-check hook defaults to `python3` (opens Microsoft Store); always commit with `PYTHON=python git commit` on Windows
- `uv sync --all-extras` — install all dependencies including dev
- `python -m pytest` — use this form (bare `pytest` is not on PATH on this Windows setup)
- `uv run pytest tests/ -v` — run tests
- `uv run ruff check src/ model/` — lint
- `uv run ruff format src/ model/` — format
- `docker compose up` — run full stack
- `python -m bratbot` — run Discord bot standalone
- `uvicorn model.app:app --port 8000` — run model API standalone
- `python scripts/test_bots.py` — manual bot test harness: sends predefined queries from `scripts/test_queries.yaml` to all 3 endpoints, outputs terminal summary + JSON. `--html` for HTML report, `--bots bratbot cami` to filter, `--base-url` for remote servers

## Deployment

- **RunPod model storage**: Ollama models persist on network volume at `/workspace/ollama` (set via `OLLAMA_MODELS` in `supervisord.runpod.conf`) — container disk can be set to 5 GB minimum
- **SSH restart from Windows fails**: `runpod-ssh-wrapper.py` can't allocate a PTY for `supervisorctl restart` — restart pods from the RunPod console instead
- **Windows**: Use `scripts/runpod-ssh-wrapper.py` for SSH commands — WSL SSH fails due to key permission issues (0777 on Windows-mounted keys)
- **New image requires pod stop/start**: `supervisorctl restart` only restarts processes in the running container; to deploy a new image, stop and start the pod from the RunPod console. **LAST RESORT ONLY** — stopping releases the RTX 4090 GPU, and it may be claimed by another user before restart. If a new dependency is missing, `pip install` it directly on the pod and restart the service via supervisorctl as a hotfix. Only stop/start the pod when absolutely necessary (e.g., base image or OS-level changes), and prefer off-peak hours (2-6 AM ET, weekends) to minimize the risk of losing the GPU
- **`pod_ssh` requires a single string command**: `pod_ssh "supervisorctl restart model bot"` works; `pod_ssh supervisorctl restart model` only sends `supervisorctl` to the remote.
- **RunPod SSH session token expires**: `RUNPOD_SSH_USER` embeds a session token that becomes stale after pod stop/restart — get the new connection string from RunPod console and update `.env.runpod`
- **Dockerfile.runpod uses editable install** (`pip install -e /app`): hatchling writes a single `.pth` file into `site-packages` that adds `/app/src` to `sys.path` at process start. This makes ALL packages under `src/` live — `/app/src/bratbot/`, `/app/src/bonniebot/`, `/app/src/common/`, etc. Editing any `.py` takes effect on next restart. **Adding a brand-new top-level package** (e.g. `common/`) requires no reinstall — just `mkdir -p /app/src/<pkg>/subdir` + curl the files; the `.pth` already covers it.
- Supervisord on pod uses `/etc/supervisor/conf.d/supervisord.conf` (not `/etc/supervisor/supervisord.conf`)
- Pod logs go to `/dev/stdout` — `supervisorctl tail` won't work; check container stdout in RunPod console
- `./scripts/deploy-runpod.sh build` — build RunPod Docker image
- `./scripts/deploy-runpod.sh push` — push to GHCR
- `./scripts/deploy-runpod.sh update` — build + push + `supervisorctl restart` (does NOT pull the new image; see "New image requires pod stop/start" above)
- `./scripts/deploy-runpod.sh hot-update` — SCP src/, model/ to running pod + restart Python services only; Ollama/GPU unaffected. Requires one full `update` first (bakes in editable install). **NOTE: SCP fails through RunPod's SSH gateway (`subsystem request failed`) — use the GitHub raw URL hotfix below instead.**
- **Code hotfix via GitHub raw URLs**: Since SCP fails through RunPod's gateway, curl files from `raw.githubusercontent.com` onto the pod instead. Commit and push first, then SSH in and run: `curl -sfL "https://raw.githubusercontent.com/z0rd0n88/bratbot/main/<path>" -o /app/<path>` + `supervisorctl restart <service>`. Pod paths mirror the repo: `src/bratbot/bot.py` → `/app/src/bratbot/bot.py`. For a **new package**, create directories first: `mkdir -p /app/src/<pkg>/{sub,dirs}` then curl each file. This is the working alternative to `hot-update`.
- **Hotfixing code + env vars go together**: Curling updated code onto the pod is only half the fix if the new code reads env vars that were never set on the pod. After a code hotfix, verify any new env vars are present (`echo $VAR_NAME`) and add them to the supervisord `[program:]` section's `environment=` directive if missing, then `supervisorctl reread && supervisorctl update <service>`.
- **Supervisord `%(ENV_VAR)s` interpolation requires the var in supervisord's OWN environment**: Pod template env vars only enter the container at container START, so supervisord (PID 1) inherits them then. For a fresh rollout where you're adding a NEW env var (e.g. the first deployment of `PROMPTS_ENCRYPTION_KEY`) to a running pod WITHOUT restarting the container (to keep the GPU), `%(ENV_NEW_VAR)s` in `supervisord.conf` won't resolve to anything because supervisord started before the var existed. The fix is a one-time hotfix: hardcode the literal value into the on-pod `/etc/supervisor/conf.d/supervisord.conf` (NOT in git — this is local-to-pod state), then `supervisorctl reread && supervisorctl update <service>`. The on-pod file gets replaced with the pristine `%(ENV_...)s` version on the next image rebuild + container restart, at which point the pod template env var flows through normally and the hotfix self-heals.
- **Personality prompts are encrypted**: `model/prompts/*.txt` are gitignored (local plaintext working copies); `model/prompts/*.txt.enc` are committed (base64-encoded PyNaCl SecretBox ciphertext). The model server decrypts them at startup using `PROMPTS_ENCRYPTION_KEY` (set in the RunPod pod template + local `.env`). **Edit workflow**: edit `model/prompts/<name>.txt` → `python scripts/encrypt-prompts.py encrypt` → commit the updated `.txt.enc` → push. In a git worktree, `.txt` files are gitignored and absent — copy from the main repo first: `cp /path/to/BratBot/model/prompts/<name>.txt model/prompts/`. Source the main repo's `.env` before encrypting: `source /path/to/BratBot/.env && PYTHON=python python scripts/encrypt-prompts.py encrypt`. **Fresh-clone recovery**: paste the key into `.env` then run `python scripts/encrypt-prompts.py decrypt` to materialize editable plaintext (or just start the model server — it decrypts at boot). **Hot-update**: curl new `.txt.enc` files via `raw.githubusercontent.com` onto `/model/prompts/` then `supervisorctl restart model`. Generate a new key with `python scripts/encrypt-prompts.py keygen` (only do this if rotating — the existing committed `.enc` files become unrecoverable). The lifespan hook in `model/app.py` loads all 3 prompts at startup so misconfiguration crashes loudly at boot, not at first user message. Tests use `BRATBOT_TEST_MODE=1` (set in `tests/conftest.py`) to bypass real decryption with sentinel strings; the crypto path itself is exercised in `tests/test_prompt_loader.py` with a fresh test key.
- `./scripts/deploy-runpod.sh ssh` — SSH into RunPod pod
- `./scripts/deploy-runpod.sh status` — check supervisord status on pod
- `./scripts/deploy-runpod.sh logs` — tail logs on pod
- RunPod config lives in `.env.runpod` (see `.env.runpod.example`)
- Two Dockerfiles: `Dockerfile` (Compose, Ollama separate) / `Dockerfile.runpod` (all-in-one with Ollama)
- **bonniebot on pod**: `supervisord.runpod.conf` runs both `bot` and `bonniebot` — restart both together: `supervisorctl restart bot bonniebot`. Restarting only `bot` leaves bonniebot stale.

## WSL Development

Windows+WSL setup is verified to work correctly:
- Git is configured with `core.autocrlf=true` (CRLF on disk → LF in working directory)
- `.gitattributes` enforces `eol=lf` for all text files, especially shell scripts
- All deployment scripts (`scripts/deploy-runpod.sh`, `scripts/runpod-entrypoint.sh`) use proper LF line endings
- Quick verification: `wsl bash scripts/deploy-runpod.sh help` (should display help without errors)
- **PowerShell via Bash tool**: `$` in inline `-Command` strings gets bash-interpolated — write PS1 to `$TEMP/script.ps1` then `powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP/script.ps1"` instead

No special WSL configuration is needed — just clone and run `./scripts/deploy-runpod.sh update` from bash/WSL.

## Conventions

- **Personality injection pattern**: Discord bots in monorepo use `Personality` dataclass attached to bot instance (`bot.personality`). Shared cogs read from it instead of module-level constants — enables multiple bot personalities without code duplication. Each bot defines its own personality file with strings + LLM endpoint.
- **Personality voice guides**: `model/prompts/<botname>.txt` defines each bot's voice, pet names, and style — reference these when writing or updating `Personality` strings in `src/<botname>/personality.py`
- User preference stores live in `common/services/` (e.g. `VerbosityStore`, `PronounStore`) — Redis key `user:{id}:{pref}`, `get_x()` returns a default if unset, `was_set()` distinguishes "user chose this" from "default"
- **Conversation history**: `ConversationHistoryStore` in `common/services/conversation_history.py` — Redis list keyed `history:{persona}:channel:{channel_id}:{user_id}`, trimmed to `history_size * 2` entries on every write. Persona names: `bratbot`, `cami`, `bonniebot`. BratBot initializes two stores (`bot.history_store` for BratBot, `bot.cami_history_store` for Cami); BonnieBot one (`bot.history_store`). History is fetched before and stored after every successful LLM call; Redis failures degrade gracefully (history skipped, bot still responds).
- Python 3.12, Ruff for linting and formatting (line-length 100)
- Ruff rules: E, F, I, UP, B, SIM
- Async everywhere (pytest-asyncio with auto mode)
- pydantic-settings for configuration, structlog for structured logging
- httpx for HTTP clients (async)
- **Age verification gate**: `check_age_verified(interaction, bot, callback)` in `utils/age_gate.py` — wraps command logic in a `_run(active_interaction)` closure. Guard runs before rate limiting. All commands except `/ping` and `/help` must use it.
- **Age gate `active_interaction`**: Inside `_run(active_interaction)`, always use `active_interaction` — on first verification it's a `button_interaction` (new interaction from the modal button), not the original slash command interaction. Mixing them causes "Unknown Interaction" errors.
- Do not edit `.env` files or `uv.lock` directly

## Gotchas

- **Monorepo bot structure**: `common.events.*` is shared by all bots; `botname.commands.*` is bot-specific. Each new bot should set `_COG_PACKAGES = ("common.events", "botname.commands")` in its `bot.py`. Bug fixes to events automatically apply to all bots — no cherry-pick needed.
- **Dependency sync**: `model/requirements.txt` is a static file used by `Dockerfile.runpod` — it must be manually updated when `pyproject.toml` dependencies change. After pushing a new image, hotfix the running pod with `pip install <pkg>` + `supervisorctl restart <service>` (since the pod won't pull the new image without a stop/start)
- Cogs auto-discovered via `pkgutil.iter_modules()` in `bot.py` — just add a file with `async def setup(bot)` to `commands/` or `events/`
- **`scripts/__init__.py` required**: The `scripts/` dir has an `__init__.py` so tests can `from scripts.test_bots import load_queries` etc. — add it when creating new importable modules in `scripts/`
- **Testing Discord commands**: `@app_commands.command` wraps the method in a `Command` object — call `.callback(cog, interaction, ...)` in tests to invoke the handler directly
- **Testing age-gated commands**: Mock `mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)` in test setup — commands call it before rate limiting, so missing it causes `AttributeError` before any assertions.
- **Redis mock**: `conftest.py` has an `async` `redis_mock` fixture (in-memory dict) — use it for any service that takes a Redis client
- **`/help` rule**: whenever a command is added, renamed, modified, or removed, update `Personality.help_text` in the relevant bot's personality file (`src/bratbot/personality.py` and/or `src/bonniebot/personality.py`) in the same commit
- **New bot services**: declare type annotation on `BratBot` class AND initialize in `setup_hook` — both required or cogs will `AttributeError` at runtime
- **`_COG_PACKAGES` silent failure**: this tuple is fed to `pkgutil.iter_modules()` at runtime, not evaluated as a Python import. If the package path is wrong (e.g. after moving a package), the bot starts cleanly but loads zero cogs — no error, just missing event handlers and commands.
- **LLMClient endpoint isolation**: Instantiate with `chat_endpoint` param (e.g., `/bratchat` for BratBot, `/bonniebot` for BonnieBot). Each bot process has its own client instance — no shared singleton.
- **Cami LLM client**: BratBot has a second client `bot.cami_llm_client` (`chat_endpoint="/camichat"`) — use it in Cami commands, not `bot.llm_client`. There is no `cami_chat()` method.
- **Cami history store**: BratBot has a second history store `bot.cami_history_store` (persona `"cami"`) — use it in Cami commands, not `bot.history_store`.
- **`LLMClient` constructor**: `LLMClient(base_url, chat_endpoint, timeout)`. The `chat()` method accepts `verbosity`, `pronoun`, and `history` as keyword-only args; `history` defaults to `[]`.
- **`/forget` persona param (BratBot)**: `ForgetCog.forget()` takes `persona: Literal["bratbot", "cami"]` and clears the corresponding store. `/forgetall` calls `history_store.clear_all()` which deletes keys for all three persona names defined in `ALL_PERSONA_NAMES` (`common/services/conversation_history.py`).
- `model/` is not a Python package (no `__init__.py`) — tests add it to `sys.path` manually
- Rate limiter degrades gracefully: if Redis is down, requests are allowed through
- All Discord-facing error messages must stay in-character (matching `bot.personality`); never expose stack traces
- Discord message limit is 2000 chars — LLMClient truncates automatically
- **Discord gateway event replay**: When discord.py's WebSocket reconnects and resumes, Discord replays recent `MESSAGE_CREATE` events — `on_message` fires twice for the same message. Guard with `deque(maxlen=1000)` of seen message IDs in the cog (see `MessageCog._processed_ids`).
- **Testing event listeners**: `@commands.Cog.listener()` methods are called directly — `await cog.on_message(message)`. No `.callback()` needed (that's only for `@app_commands.command` slash commands).
- **`is_done()` mock trap**: `InteractionResponse.is_done()` is synchronous — use `MagicMock(return_value=False)`, NOT `AsyncMock()`. AsyncMock returns a coroutine (always truthy), breaking `_reply()` routing and conditional defer logic.
- **Testing `discord.ui.View` buttons**: Get the button from `view.children[0]` and call `await button.callback(interaction)` — do NOT call the decorated method directly (discord.py wraps it in `_ItemCallback`)
- **`ruff check` ≠ `ruff format`**: lint can pass while formatter still wants changes (e.g. implicit string concatenation style) — always run both before committing
- **Ollama cold start on fresh pod**: Model takes ~103s to load from network volume into VRAM. `model/app.py` starts `_do_warmup()` as a background asyncio task and gates all chat endpoints on `_model_ready` flag. While warming, endpoints return `503 {"status":"warming_up"}`; bots catch this as `LLMWarmingError` and reply with `bot.personality.llm_warming_up_reply`.
- **LLM error hierarchy**: `LLMError` → `LLMConnectionError`, `LLMTimeoutError`, `LLMServerError`, `LLMValidationError`, `LLMWarmingError` (503 warming_up). All live in `services/llm_client.py`; `errors.py` maps them to personality strings; commands also catch them inline.
- **Response variety system**: `model/app.py` injects a per-request mood from `BRAT_MOODS`/`CAMI_MOODS`/`BONNIE_MOODS` and sets `repeat_penalty=1.2`, `repeat_last_n=256` on all Ollama payloads — these work together to prevent repetitive replies; preserve both when editing the model server
- **Prompt variety directives**: `model/prompts/*.txt` files end with a `## RESPONSE VARIETY RULES` section — preserve this when revising personality prompts
- **model/app.py field gap**: When adding a new field to `LLMClient`'s payload, also add it to `ChatRequest`, `CamiChatRequest`, and `BonnieChatRequest` in `model/app.py` — Pydantic silently drops unknown fields (no 422 error), so the field is missing in the endpoint handler with no warning.
- **conftest.py env var stubs**: `bratbot.config.settings` is instantiated at import time — any test that imports a module chaining to it (`RateLimiter`, `request_queue`, `age_gate`) needs `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_ID`, `LLM_API_URL`, `REDIS_URL` set. `conftest.py` now provides all four via `os.environ.setdefault()`.
- **Feature removal checklist**: when removing a command, check README.md, CLAUDE.md, .env.example, .env.runpod.example, docs/terms.html, and docs/privacy.html — all store feature-specific content that must be cleaned up
- **Manual test checklist**: `docs/MANUAL_TESTING.md` lists every feature with exact steps and expected results; update it when adding/removing commands (a PostToolUse hook reminds you automatically when writing to `src/*/commands/` or `src/common/events/`)
