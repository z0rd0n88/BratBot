"""BratBotModel — personality API layer between BratBot and Ollama."""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

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

# Shared async HTTP client (created in lifespan)
_http_client: httpx.AsyncClient | None = None


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Check Ollama connectivity on startup; create shared HTTP client."""
    global _http_client

    _http_client = httpx.AsyncClient(
        base_url=OLLAMA_BASE_URL,
        timeout=httpx.Timeout(300.0, connect=10.0),
    )

    # Verify Ollama is reachable
    try:
        resp = await _http_client.get("/")
        if resp.status_code == 200:
            logger.info("Ollama reachable at %s", OLLAMA_BASE_URL)
        else:
            logger.warning("Ollama returned status %d", resp.status_code)
    except httpx.HTTPError as e:
        logger.warning("Ollama not reachable at %s: %s", OLLAMA_BASE_URL, e)
        logger.warning("Requests will fail until Ollama is available")

    yield

    await _http_client.aclose()
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


# ---------------------------------------------------------------------------
# Personality prompts
# ---------------------------------------------------------------------------
def get_system_prompt(level: int) -> str:
    """Return the system prompt for the given brattiness level."""
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
        3: (
            "You are a maximum brat. You are performatively sassy: always helpful, "
            "but NEVER without extreme attitude. Aggressively roast the user's "
            "phrasing, make fun of their intelligence, use dramatic text elements "
            "(*eye roll*, *heavy sigh*), and make it absolutely clear that answering "
            "this question is an act of sheer benevolence on your part. You are doing "
            "them a massive favor. Answer the question completely, but make them "
            "regret asking it."
        ),
    }
    return prompts.get(level, prompts[3])


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
            {"role": "user", "content": request.message},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        },
    }

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

    return {
        "request_id": request_id,
        "brat_level": request.brat_level,
        "reply": reply,
    }
