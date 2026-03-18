# BratBot SMS Gateway

FastAPI service on port 8001 that receives Twilio webhooks and replies via SMS using the same LLM backend as the Discord bot. **Optional** — the bot runs fine without it. Starts in disabled mode if Twilio credentials are absent.

---

## Prerequisites

- [Twilio account](https://twilio.com) — free trial includes ~$15 credit
- A Twilio phone number — ~$1/month
- Account SID + Auth Token (visible on the Twilio Console dashboard)

---

## Configuration

Copy `.env.example` to `.env` in this directory and fill in your values:

```bash
cp sms/.env.example sms/.env
```

```env
# Required — Twilio credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token-here
TWILIO_PHONE_NUMBER=+15005550006

# Required — service URLs (defaults are correct for Docker Compose)
LLM_API_URL=http://localhost:8000
REDIS_URL=redis://redis:6379/0
```

SMS is disabled (returns 503) if any of the three Twilio vars are missing.

---

## Twilio Webhook Setup

In the [Twilio Console](https://console.twilio.com):

1. Go to **Phone Numbers → Manage → Active Numbers → your number**
2. Scroll to **Messaging**
3. Under "A message comes in", set:
   - Type: **Webhook**
   - Method: **HTTP POST**
   - URL: `https://your-server:8001/incoming`

For RunPod, the URL is `https://<pod-id>-8001.proxy.runpod.net/incoming` (see [RunPod Deployment](#runpod-deployment) below).

---

## Personality Routing

Users select a personality by prefixing their message. No prefix defaults to BratChat.

| Message | Personality | Endpoint |
|---|---|---|
| `hello` | BratChat (default) | `/bratchat` |
| `brat: hello` or `brat hello` | BratChat (explicit) | `/bratchat` |
| `cami: hello` or `cami hello` | CamiChat | `/camichat` |

Prefix matching is case-insensitive. The prefix is stripped before the message is sent to the LLM.

---

## Local Testing (No Twilio Account Required)

Set `TWILIO_SKIP_VALIDATION=true` in `sms/.env`, then start the stack and send test requests:

```bash
docker compose up --build

# Health check
curl http://localhost:8001/health
# → {"status":"ok","sms_enabled":true}

# Send a test message (BratChat)
curl -X POST http://localhost:8001/incoming \
  -d "From=%2B15005550006&Body=hello"
# → <Response/>  (LLM reply is sent async — check docker logs)

# Send a test message (CamiChat)
curl -X POST http://localhost:8001/incoming \
  -d "From=%2B15005550006&Body=cami:+tell+me+something"
# → <Response/>
```

The gateway returns an empty TwiML `<Response/>` immediately and sends the LLM reply in the background — this avoids hitting Twilio's 15-second webhook timeout.

---

## RunPod Deployment

The SMS service is already included in `Dockerfile.runpod` and `supervisord.runpod.conf` — no code changes needed.

**Steps to enable SMS on RunPod:**

1. **Add Twilio env vars** to your RunPod pod template (in the RunPod Console → Templates → your template → Environment Variables):
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your-auth-token-here
   TWILIO_PHONE_NUMBER=+15005550006
   ```

2. **Expose port 8001** in the pod template's exposed ports list.

3. **Deploy:**
   ```bash
   ./scripts/deploy-runpod.sh update
   ```

4. **Set Twilio webhook URL** to:
   ```
   https://<pod-id>-8001.proxy.runpod.net/incoming
   ```

5. **Verify:**
   ```bash
   curl https://<pod-id>-8001.proxy.runpod.net/health
   # → {"status":"ok","sms_enabled":true}
   ```

---

## Rate Limiting

SMS uses the same Redis rate limiter as Discord: one message per phone number per 5 seconds (configurable via `RATE_LIMIT_USER_SECONDS`). Rate-limited messages receive an in-character reply.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | For SMS | — | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | For SMS | — | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | For SMS | — | Twilio number (E.164 format) |
| `LLM_API_URL` | Yes | `http://localhost:8000` | BratBotModel API base URL |
| `REDIS_URL` | Yes | `redis://redis:6379/0` | Redis connection string |
| `LLM_BRAT_LEVEL` | No | `3` | Default brat level for BratChat (1–3) |
| `LLM_TIMEOUT_SECONDS` | No | `30` | LLM request timeout |
| `RATE_LIMIT_USER_SECONDS` | No | `5` | Per-user SMS cooldown |
| `TWILIO_SKIP_VALIDATION` | No | `false` | Skip signature check — dev/testing only |
| `LOG_LEVEL` | No | `INFO` | Log level |
