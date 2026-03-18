"""BratBot SMS Gateway — receives Twilio webhooks and replies via SMS."""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient

from settings import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bratbot-sms")

# Message length limit for SMS (Twilio concatenates multi-part, but cap at ~1600 chars)
_SMS_MAX_LENGTH = 1600

# In-character replies
_RATE_LIMITED_REPLY = "Slow down. I have better things to do."
_LLM_ERROR_REPLY = "Something went wrong with my brain. Try again, or don't. I don't care."
_EMPTY_MESSAGE_REPLY = "You texted me nothing? Wow. Bold strategy."

# ---------------------------------------------------------------------------
# Shared clients (initialized in lifespan)
# ---------------------------------------------------------------------------
_http_client: httpx.AsyncClient | None = None
_redis_client: aioredis.Redis | None = None
_twilio_client: TwilioClient | None = None
_validator: RequestValidator | None = None


def _sms_configured() -> bool:
    """Return True if all required Twilio credentials are present."""
    return bool(
        settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client, _redis_client, _twilio_client, _validator

    _http_client = httpx.AsyncClient(
        base_url=settings.llm_api_url,
        timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=5.0),
    )
    _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

    if _sms_configured():
        _twilio_client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        _validator = RequestValidator(settings.twilio_auth_token)
        logger.info(
            "SMS gateway started — llm_api_url=%s number=%s",
            settings.llm_api_url,
            settings.twilio_phone_number,
        )
        if settings.twilio_skip_validation:
            logger.warning("TWILIO_SKIP_VALIDATION=true — signature checking disabled")
    else:
        logger.warning(
            "SMS gateway started in DISABLED mode — "
            "set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to enable"
        )

    yield

    await _http_client.aclose()
    await _redis_client.aclose()
    _http_client = None
    _redis_client = None
    _twilio_client = None
    _validator = None


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _is_rate_limited(phone: str) -> bool:
    """Return True if this phone number has exceeded the per-user rate limit.

    Uses the same Redis INCR + EXPIRE atomic pattern as the Discord rate limiter
    (src/bratbot/services/rate_limiter.py).
    """
    key = f"ratelimit:sms:user:{phone}"
    async with _redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, settings.rate_limit_user_seconds)
        results = await pipe.execute()
    count = results[0]
    if count > 1:
        ttl = await _redis_client.ttl(key)
        logger.debug("rate_limit_hit phone=%s count=%d retry_after=%d", phone, count, ttl)
        return True
    return False


def _send_sms(to: str, body: str) -> None:
    """Send an outbound SMS via the Twilio REST API."""
    _twilio_client.messages.create(
        to=to,
        from_=settings.twilio_phone_number,
        body=body[:_SMS_MAX_LENGTH],
    )


def _parse_route(body: str) -> tuple[str, str, dict]:
    """Parse an optional personality prefix from the message body.

    Supports "cami: ...", "cami ...", "brat: ...", "brat ..." (case-insensitive).
    Returns (endpoint, clean_message, extra_payload).
    """
    stripped = body.strip()
    lower = stripped.lower()

    for prefix, endpoint, extra in (
        ("cami", "/camichat", {}),
        ("brat", "/bratchat", {"brat_level": settings.llm_brat_level}),
    ):
        if lower.startswith(prefix):
            rest = stripped[len(prefix) :]
            if rest and rest[0] in (":", " "):
                clean = rest.lstrip(": ")
                if clean:
                    return endpoint, clean, extra

    return "/bratchat", stripped, {"brat_level": settings.llm_brat_level}


async def _process_sms(from_number: str, body: str) -> None:
    """Background task: rate-limit check → LLM call → send reply."""
    logger.info("sms_received from=%s body_len=%d", from_number, len(body))

    if await _is_rate_limited(from_number):
        logger.info("sms_rate_limited from=%s", from_number)
        await asyncio.to_thread(_send_sms, from_number, _RATE_LIMITED_REPLY)
        return

    endpoint, clean_body, extra = _parse_route(body)
    payload = {"message": clean_body[:2000], **extra}

    try:
        resp = await _http_client.post(endpoint, json=payload)
        resp.raise_for_status()
        reply = resp.json().get("reply", _LLM_ERROR_REPLY)
        logger.info(
            "sms_reply_ready from=%s endpoint=%s reply_len=%d", from_number, endpoint, len(reply)
        )
    except Exception as exc:
        logger.error("sms_llm_error from=%s error=%s", from_number, exc)
        reply = _LLM_ERROR_REPLY

    await asyncio.to_thread(_send_sms, from_number, reply)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    configured = _sms_configured()
    return {"status": "ok", "sms_enabled": configured}


@app.post("/incoming")
async def incoming_sms(request: Request, background_tasks: BackgroundTasks):
    """Receive an inbound SMS from Twilio.

    Returns an empty TwiML <Response/> immediately so Twilio's 15-second
    webhook timeout is never hit. The actual LLM call and reply are handled
    as a background task.
    """
    if not _sms_configured():
        raise HTTPException(status_code=503, detail="SMS not configured")

    form = await request.form()
    from_number: str = form.get("From", "")
    body: str = form.get("Body", "").strip()

    # Validate Twilio signature to reject forged requests
    if not settings.twilio_skip_validation:
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        post_params = dict(form)
        if not _validator.validate(url, post_params, signature):
            logger.warning("invalid_twilio_signature from=%s", from_number)
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    if not from_number:
        raise HTTPException(status_code=400, detail="Missing From field")

    if not body:
        logger.info("sms_empty_body from=%s", from_number)
        background_tasks.add_task(_send_sms, from_number, _EMPTY_MESSAGE_REPLY)
        return Response(content="<Response/>", media_type="text/xml")

    background_tasks.add_task(_process_sms, from_number, body)

    # Return empty TwiML immediately — actual reply is sent via Twilio REST API
    return Response(content="<Response/>", media_type="text/xml")
