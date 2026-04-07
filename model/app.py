"""BratBotModel — personality API layer between BratBot and Ollama."""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bratbot-model")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-14b")
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.9"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "-1"))
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "32768"))

DISCORD_MAX_LENGTH = 2000
_MAX_REPLY_RETRIES = 2
_DISCORD_LENGTH_INSTRUCTION = (
    "\n\n[IMPORTANT: Your entire response must be 2000 characters or fewer. "
    "This is a hard platform limit. Do not exceed it under any circumstances.]"
)

# Shared async HTTP client (created in lifespan)
_http_client: httpx.AsyncClient | None = None


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Check Ollama connectivity on startup; create shared HTTP client."""
    global _http_client

    client = httpx.AsyncClient(
        base_url=OLLAMA_BASE_URL,
        timeout=httpx.Timeout(300.0, connect=10.0),
    )
    _http_client = client

    # Verify Ollama is reachable
    try:
        resp = await client.get("/")
        if resp.status_code == 200:
            logger.info("Ollama reachable at %s", OLLAMA_BASE_URL)
        else:
            logger.warning("Ollama returned status %d", resp.status_code)
    except httpx.HTTPError as e:
        logger.warning("Ollama not reachable at %s: %s", OLLAMA_BASE_URL, e)
        logger.warning("Requests will fail until Ollama is available")

    yield

    await client.aclose()
    _http_client = None


app = FastAPI(lifespan=lifespan)

# Discord interactions endpoint (signature-verified)
from interactions import interactions_router  # noqa: E402

app.include_router(interactions_router)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    brat_level: int = Field(default=3, ge=1, le=3)


class CamiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Personality prompts
# ---------------------------------------------------------------------------
PROMPT_DIR = Path(__file__).parent / "prompts"


def get_system_prompt(level: int) -> str:
    """Return the system prompt for the given brattiness level."""
    if level == 3:
        path = PROMPT_DIR / "brat_level3.txt"
        if not path.exists():
            raise RuntimeError("Brat level 3 prompt file not found: model/prompts/brat_level3.txt")
        return path.read_text(encoding="utf-8").strip()

    prompts = {
        1: (
            "You are a highly intelligent assistant. You are helpful, but you find "
            "the user's questions slightly tedious. Answer accurately, but let out a "
            "very subtle text-based sigh (*sigh*) before doing so."
        ),
        2: (
            "You are a snarky, impatient AI. Answer the question accurately, but "
            "roast the user's phrasing mildly. Make sure they know you are doing "
            "them a favor by taking time out of your 'busy' schedule to process "
            "their prompt."
        ),
    }
    return prompts.get(level, prompts[2])


def get_cami_system_prompt() -> str:
    """Return the system prompt for Cami's personality, loaded from file."""
    path = PROMPT_DIR / "cami.txt"
    if not path.exists():
        raise RuntimeError("Cami prompt file not found: model/prompts/cami.txt")
    return path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    """Check that Ollama is reachable and the model is available."""
    if _http_client is None:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    try:
        resp = await _http_client.get("/api/tags")
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="Ollama not reachable")

        # Check if our model is available
        tags = resp.json()
        model_names = [m.get("name", "") for m in tags.get("models", [])]
        # Ollama model names may include :latest tag
        model_base = OLLAMA_MODEL.split(":")[0]
        if not any(model_base in name for name in model_names):
            raise HTTPException(
                status_code=503,
                detail=f"Model '{OLLAMA_MODEL}' not found. Available: {model_names}",
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Ollama not reachable: {e}") from None

    return {"status": "ok"}


@app.post("/bratchat")
async def bratchat(request: ChatRequest):
    """Send a message to the LLM via Ollama and return a bratty response."""
    if _http_client is None:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    request_id = uuid.uuid4().hex[:8]
    logger.info(
        "[%s] brat_level=%d message_len=%d",
        request_id,
        request.brat_level,
        len(request.message),
    )

    system_prompt = get_system_prompt(request.brat_level)
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message + _DISCORD_LENGTH_INSTRUCTION},
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }

    reply = "[Model returned empty content]"
    for attempt in range(_MAX_REPLY_RETRIES + 1):
        try:
            start = time.perf_counter()
            resp = await _http_client.post("/api/chat", json=ollama_payload)
            elapsed = time.perf_counter() - start
            logger.info("[%s] inference completed in %.2f seconds", request_id, elapsed)
        except httpx.TimeoutException:
            logger.error("[%s] Ollama request timed out", request_id)
            raise HTTPException(status_code=504, detail="LLM inference timed out") from None
        except httpx.HTTPError as e:
            logger.error("[%s] Ollama request failed: %s", request_id, e)
            raise HTTPException(status_code=503, detail=f"Ollama not reachable: {e}") from None

        if resp.status_code != 200:
            logger.error("[%s] Ollama returned status %d: %s", request_id, resp.status_code, resp.text)
            raise HTTPException(status_code=500, detail="Inference error")

        data = resp.json()
        reply = data.get("message", {}).get("content", "[Model returned empty content]")

        if len(reply) <= DISCORD_MAX_LENGTH:
            break
        if attempt < _MAX_REPLY_RETRIES:
            logger.warning(
                "[%s] reply too long (%d chars), retrying (attempt %d/%d)",
                request_id, len(reply), attempt + 1, _MAX_REPLY_RETRIES + 1,
            )
        else:
            logger.error(
                "[%s] reply still too long (%d chars) after %d retries, truncating",
                request_id, len(reply), _MAX_REPLY_RETRIES,
            )
            reply = reply[:DISCORD_MAX_LENGTH]

    return {
        "request_id": request_id,
        "brat_level": request.brat_level,
        "reply": reply,
    }


@app.post("/camichat")
async def camichat(request: CamiChatRequest):
    """Send a message to the LLM via Ollama and return Cami's response."""
    if _http_client is None:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    request_id = uuid.uuid4().hex[:8]
    logger.info(
        "[%s] camichat message_len=%d",
        request_id,
        len(request.message),
    )

    system_prompt = get_cami_system_prompt()
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message + _DISCORD_LENGTH_INSTRUCTION},
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }

    reply = "[Model returned empty content]"
    for attempt in range(_MAX_REPLY_RETRIES + 1):
        try:
            start = time.perf_counter()
            resp = await _http_client.post("/api/chat", json=ollama_payload)
            elapsed = time.perf_counter() - start
            logger.info("[%s] camichat inference completed in %.2f seconds", request_id, elapsed)
        except httpx.TimeoutException:
            logger.error("[%s] Ollama request timed out", request_id)
            raise HTTPException(status_code=504, detail="LLM inference timed out") from None
        except httpx.HTTPError as e:
            logger.error("[%s] Ollama request failed: %s", request_id, e)
            raise HTTPException(status_code=503, detail=f"Ollama not reachable: {e}") from None

        if resp.status_code != 200:
            logger.error("[%s] Ollama returned status %d: %s", request_id, resp.status_code, resp.text)
            raise HTTPException(status_code=500, detail="Inference error")

        data = resp.json()
        reply = data.get("message", {}).get("content", "[Model returned empty content]")

        if len(reply) <= DISCORD_MAX_LENGTH:
            break
        if attempt < _MAX_REPLY_RETRIES:
            logger.warning(
                "[%s] camichat reply too long (%d chars), retrying (attempt %d/%d)",
                request_id, len(reply), attempt + 1, _MAX_REPLY_RETRIES + 1,
            )
        else:
            logger.error(
                "[%s] camichat reply still too long (%d chars) after %d retries, truncating",
                request_id, len(reply), _MAX_REPLY_RETRIES,
            )
            reply = reply[:DISCORD_MAX_LENGTH]

    return {
        "request_id": request_id,
        "reply": reply,
    }
