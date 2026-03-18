# SMS/RCS Implementation Plan

> **Branch:** `sms`
> **Status:** Ready for implementation
> **Created:** 2026-03-18

---

## Overview

Add SMS/RCS support to BratBot so users can text the bot and receive the same bratty personality responses as Discord. SMS must be **optional** — deploying without SMS configured is fully supported.

### Design Decisions (Already Made)

| Decision | Choice | Rationale |
|---|---|---|
| SMS Provider | **Twilio** | Mature API, SMS+RCS support, webhook-based, free trial |
| iMessage | **Skipped** | Proprietary, requires Mac infrastructure |
| Architecture | **Unified** | All channels (Discord, SMS) share the same LLM backend |
| Identity | **Phone number** | E.164 format, used as rate limit key |
| Rate limiting | **Same as Discord** | 5s per-user cooldown, Redis fixed-window |
| Optional deploy | **Yes** | SMS gateway starts in disabled mode if Twilio creds missing |

---

## Current State (What Already Exists)

The SMS gateway is **already implemented** on the `sms` branch. Here's what exists:

### Files Already Created

| File | Status | Description |
|---|---|---|
| `sms/app.py` | **Done** | FastAPI gateway — Twilio webhook receiver, rate limiting, LLM integration |
| `sms/settings.py` | **Done** | pydantic-settings config — Twilio creds optional (defaults to `None`) |
| `sms/.env.example` | **Done** | Template with all SMS env vars documented |
| `sms/requirements.txt` | **Done** | `fastapi`, `uvicorn`, `httpx`, `redis`, `twilio`, `pydantic-settings` |
| `supervisord.conf` | **Updated** | Added `[program:sms]` on port 8001, priority=3 |
| `supervisord.runpod.conf` | **Updated** | Added `[program:sms]` on port 8001, priority=3 |
| `Dockerfile` | **Updated** | Stage 3 builds SMS deps, copies `sms/app.py` + `sms/settings.py` |
| `Dockerfile.runpod` | **Updated** | Same SMS build stage, exposes 8001 |
| `docker-compose.yml` | **Updated** | `sms/.env` loaded (required: false), port 8001 exposed |
| `README.md` | **Updated** | Architecture diagram, SMS setup section, env var table, troubleshooting |

### Architecture (Already Working)

```
User texts Twilio number
  → Twilio POSTs to https://your-server:8001/incoming
  → SMS Gateway validates Twilio signature
  → Rate-limits by phone number (Redis)
  → POSTs to http://localhost:8000/bratchat (same as Discord)
  → BratBotModel → Ollama → LLM reply
  → Twilio REST API sends SMS reply back to user
```

### Key Implementation Details

1. **Optional SMS** — `_sms_configured()` checks if all 3 Twilio vars are set. If not, gateway starts in disabled mode, `/incoming` returns 503, `/health` returns `{"sms_enabled": false}`
2. **Background processing** — Returns empty `<Response/>` TwiML immediately to avoid Twilio's 15s webhook timeout. LLM call + reply happen in a FastAPI background task
3. **Rate limiting** — Uses same Redis INCR+EXPIRE pattern as Discord (`ratelimit:sms:user:{phone}`, 5s window)
4. **Message length** — SMS capped at 1600 chars (Twilio concatenates multi-part beyond that)
5. **Signature validation** — Twilio `RequestValidator` verifies webhook authenticity. `TWILIO_SKIP_VALIDATION=true` for dev/testing only

---

## What Still Needs to Be Done

### Step 1: Write Tests for SMS Gateway

**Priority: High** — No tests exist for `sms/app.py` yet.

**File to create:** `tests/test_sms_gateway.py`

**Test cases needed:**

1. **Health endpoint**
   - `GET /health` returns `{"status": "ok", "sms_enabled": true}` when configured
   - `GET /health` returns `{"status": "ok", "sms_enabled": false}` when unconfigured

2. **Incoming SMS — happy path**
   - Valid Twilio webhook → 200 with empty `<Response/>` TwiML
   - Background task calls `/bratchat` and sends SMS reply

3. **Incoming SMS — validation**
   - Missing `From` field → 400
   - Empty `Body` → sends `_EMPTY_MESSAGE_REPLY` via background task
   - Invalid Twilio signature → 403
   - Signature check skipped when `TWILIO_SKIP_VALIDATION=true`

4. **Rate limiting**
   - First request allowed, second within 5s window rate-limited
   - Rate-limited → sends `_RATE_LIMITED_REPLY`

5. **LLM error handling**
   - LLM timeout → sends `_LLM_ERROR_REPLY`
   - LLM 5xx → sends `_LLM_ERROR_REPLY`

6. **SMS disabled mode**
   - `/incoming` returns 503 when Twilio creds not set

**Testing approach:**
- Use `httpx.AsyncClient` with FastAPI's `TestClient` (or `httpx.ASGITransport`)
- Mock Twilio client (`_twilio_client`) and HTTP client (`_http_client`) via monkeypatching module globals
- Mock Redis with `fakeredis` (already a pattern if used elsewhere) or mock the `_redis_client` global
- Since `sms/` is not a Python package (no `__init__.py`), add it to `sys.path` in conftest (same pattern as `model/` tests)

**Important notes:**
- `sms/app.py` uses module-level globals (`_http_client`, `_redis_client`, etc.) initialized in lifespan — tests need to either trigger lifespan or monkeypatch globals directly
- Twilio signature validation uses the request URL, so test URL must be deterministic

### Step 2: Add SMS Tests to CI/Lint

**Files to update:** None expected — existing `uv run pytest tests/ -v` should pick up new test file automatically.

**Verify:**
- `uv run ruff check sms/` — lint SMS gateway code
- `uv run pytest tests/ -v` — confirm new tests pass
- Check if `sms/` needs to be added to ruff's include paths in `pyproject.toml`

### Step 3: End-to-End Testing with Twilio

**Manual verification steps:**

1. **Local testing (no Twilio account needed):**
   ```bash
   # Start stack
   docker compose up --build

   # Check health
   curl http://localhost:8001/health
   # → {"status": "ok", "sms_enabled": false}  (no creds)

   # Set TWILIO_SKIP_VALIDATION=true in sms/.env, restart
   curl -X POST http://localhost:8001/incoming \
     -d "From=%2B15005550006&Body=hello"
   # → <Response/> (check logs for LLM call)
   ```

2. **With Twilio (real SMS):**
   - Configure `sms/.env` with real Twilio credentials
   - Expose port 8001 via ngrok or deploy to RunPod
   - Set Twilio webhook URL to `https://your-server:8001/incoming`
   - Text the Twilio number from a phone
   - Verify bratty response arrives as SMS

### Step 4: RunPod Deployment Changes

**Pod template changes needed:**

1. **Expose port 8001** — Add `8001/http` to pod template's exposed ports
2. **Add Twilio env vars** (only if enabling SMS):
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_PHONE_NUMBER`
3. **Rebuild and deploy:** `./scripts/deploy-runpod.sh update`

**No code changes needed** — env vars are read from the container environment by pydantic-settings.

### Step 5: Optional Enhancements (Future)

These are not blockers but nice-to-haves for later:

1. **Conversation history for SMS** — Currently stateless (single-turn). Could store recent messages in Redis keyed by phone number for multi-turn context.
2. **RCS rich media** — Twilio supports RCS on Android. Could send rich cards, carousels, etc. Requires Twilio RCS channel config.
3. **MMS support** — Handle incoming images/media (currently ignored by the gateway).
4. **Per-phone brat level** — Let users text "brat level 2" to change their default. Would need Redis-backed user preferences.
5. **Opt-out support** — Handle STOP/HELP keywords (Twilio handles some automatically, but custom responses could stay in character).
6. **Webhook URL validation** — Add a Twilio webhook URL validation endpoint for easier setup.

---

## File Reference

### Files to Read Before Implementing

| File | Why |
|---|---|
| `sms/app.py` | The SMS gateway — what you're testing |
| `sms/settings.py` | Configuration — understand optional fields |
| `tests/test_llm_client.py` | Testing patterns already used in the project |
| `tests/conftest.py` | Shared fixtures, sys.path setup |
| `src/bratbot/services/rate_limiter.py` | Rate limiting pattern to match |
| `model/app.py` | LLM API endpoints the gateway calls |

### Files That May Need Changes

| File | Change |
|---|---|
| `tests/test_sms_gateway.py` | **Create** — all SMS tests |
| `tests/conftest.py` | **Maybe update** — add `sms/` to sys.path |
| `pyproject.toml` | **Maybe update** — add `sms/` to ruff include paths |

---

## Provider Comparison (For Reference)

The user chose Twilio. Here's the comparison that was considered:

| Provider | SMS | RCS | Pricing | Notes |
|---|---|---|---|---|
| **Twilio** (chosen) | Yes | Yes (Android) | ~$0.0079/msg + $1/mo/number | Most mature, best docs, webhook-based |
| Vonage (Nexmo) | Yes | Yes | ~$0.0068/msg | Similar webhook model |
| MessageBird | Yes | Yes | ~$0.007/msg | EU-focused |
| Amazon SNS | Yes | No | ~$0.00645/msg | No RCS, no webhook (poll-based) |
| Google Business Messages | No | Yes | Free | RCS only, requires business verification |

---

## Quick Start for New Session

If starting a new Claude Code session on the `sms` branch:

1. Read this plan first
2. The SMS gateway is already implemented — focus on **Step 1 (tests)** and **Step 2 (CI/lint)**
3. All design decisions are already made (see table at top)
4. Key files: `sms/app.py`, `sms/settings.py`, `tests/test_llm_client.py` (for test patterns)
5. Deploy is optional via RunPod — see Step 4
