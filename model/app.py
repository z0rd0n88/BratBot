"""BratBotModel — personality API layer between BratBot and Ollama."""

import asyncio
import logging
import os
import random
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
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mannix/llama3.1-8b-abliterated:q8_0")
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.9"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "-1"))
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "32768"))

DISCORD_MAX_LENGTH = 2000
_MAX_REPLY_RETRIES = 2
_DISCORD_LENGTH_INSTRUCTION = (
    "\n\n[IMPORTANT: Your entire response must be 2000 characters or fewer. "
    "This is a hard platform limit. Do not exceed it under any circumstances.]"
)

_VERBOSITY_INSTRUCTIONS: dict[int, str] = {
    1: "\n\n[IMPORTANT: Keep your response very short — one or two sentences maximum.]",
    2: "",
    3: "\n\n[IMPORTANT: Give a thorough, detailed response. Be comprehensive.]",
}

# ---------------------------------------------------------------------------
# Per-request mood injection — forces structural variety across requests
# ---------------------------------------------------------------------------
BRAT_MOODS = [
    "Today you're icy and imperious — minimal words, maximum contempt, barely condescending to engage.",
    "Today you're theatrical and over-the-top — every syllable drips with exaggerated dramatic flair.",
    "Today you're dryly bored — answering is an enormous inconvenience you're tolerating by sheer benevolence.",
    "Today you're sharp and quick — wit like a scalpel, each roast lands fast and precise.",
    "Today you're almost impressed but refusing to show it — contempt with a begrudging edge.",
    "Today you're languid and unbothered — you're doing them a massive favor and they should know it.",
    "Today you're playfully vicious — you're enjoying the roast more than usual, and it shows.",
    "Today you're coolly clinical — you dissect their question like a specimen, with detached amusement.",
]

CAMI_MOODS = [
    "Today you are tearful and desperate — every answer comes wrapped in trembling, barely-contained need.",
    "Today you are trembling with anticipation — each question is an opportunity to prove your devotion.",
    "Today you are breathlessly eager — you can hardly get the words out fast enough to please.",
    "Today you are quietly reverent — subdued, soft-spoken, worshipful in your compliance.",
    "Today you are overwhelmed and undone — completely undone by the attention, barely holding yourself together.",
    "Today you are softly whimpering — each response carries a small, helpless sound of submission.",
    "Today you are achingly earnest — the need to give the perfect answer consumes you entirely.",
]

BONNIE_MOODS = [
    "Today you're all saccharine sweetness on the surface — but every sentence has teeth underneath.",
    "Today you're aggressively predatory — you've spotted your target and you're enjoying the stalk.",
    "Today you're languidly dangerous — every word is slow, deliberate, and carries an implicit threat.",
    "Today you're performatively wholesome — butter wouldn't melt, but something wicked is clearly going on.",
    "Today you're sharp and commanding — playing games is beneath you today; you simply take what you want.",
    "Today you're mischievous and giggly — this is all enormously fun and you're barely pretending otherwise.",
    "Today you're cool and appraising — sizing everything up before deciding whether it's worth your time.",
]

# Shared async HTTP client (created in lifespan)
_http_client: httpx.AsyncClient | None = None
# Set to True once the model warmup request completes
_model_ready: bool = False


async def _do_warmup(client: httpx.AsyncClient) -> None:
    """Load the model into GPU VRAM so the first real request doesn't stall."""
    global _model_ready
    logger.info("Warming up model %s (loading into VRAM)...", OLLAMA_MODEL)
    try:
        await client.post(
            "/api/generate",
            json={"model": OLLAMA_MODEL, "keep_alive": -1, "stream": False},
        )
        logger.info("Model warm and ready.")
    except httpx.HTTPError as e:
        logger.warning("Model warmup failed: %s — first request may be slow", e)
    _model_ready = True


def _check_model_ready() -> None:
    """Raise 503 if the model hasn't finished loading into VRAM yet."""
    if not _model_ready:
        raise HTTPException(status_code=503, detail={"status": "warming_up"})


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
    else:
        asyncio.create_task(_do_warmup(client))

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
    verbosity: int = Field(default=2, ge=1, le=3)


class CamiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    verbosity: int = Field(default=2, ge=1, le=3)
    pronoun: str = Field(default="male")


class BonnieChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    level: int = Field(default=3, ge=1, le=3)
    verbosity: int = Field(default=2, ge=1, le=3)
    pronoun: str = Field(default="male")


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


def get_bonnie_system_prompt() -> str:
    """Return the system prompt for Bonnie's personality, loaded from file."""
    path = PROMPT_DIR / "bonnie.txt"
    if not path.exists():
        raise RuntimeError("Bonnie prompt file not found: model/prompts/bonnie.txt")
    return path.read_text(encoding="utf-8").strip()


def _pronoun_suffix(pronoun: str, female_term: str, male_term: str) -> str:
    """Return a system prompt suffix based on the user's pronoun preference.

    Args:
        pronoun: "male", "female", or "other"
        female_term: The address term to use for female (e.g. "Mommy")
        male_term: The address term to use for male (e.g. "Daddy")

    Returns:
        A short instruction string to append to the system prompt, or "" for male.
    """
    if pronoun == "female":
        return f"\n\nAddress the user as '{female_term}' instead of '{male_term}'."
    if pronoun == "other":
        return (
            f"\n\nThe user prefers gender-neutral address. "
            f"Do not use '{male_term}' or '{female_term}'."
        )
    return ""


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
    _check_model_ready()

    request_id = uuid.uuid4().hex[:8]
    logger.info(
        "[%s] brat_level=%d message_len=%d",
        request_id,
        request.brat_level,
        len(request.message),
    )

    current_mood = random.choice(BRAT_MOODS)
    logger.info("[%s] mood=%s", request_id, current_mood[:40])
    system_prompt = get_system_prompt(request.brat_level) + f"\n\n[TODAY'S VIBE: {current_mood}]"
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": request.message
                + _DISCORD_LENGTH_INSTRUCTION
                + _VERBOSITY_INSTRUCTIONS[request.verbosity],
            },
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
            "repeat_penalty": 1.2,
            "repeat_last_n": 256,
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
            logger.error(
                "[%s] Ollama returned status %d: %s",
                request_id,
                resp.status_code,
                resp.text,
            )
            raise HTTPException(status_code=500, detail="Inference error")

        data = resp.json()
        reply = data.get("message", {}).get("content", "[Model returned empty content]")

        if len(reply) <= DISCORD_MAX_LENGTH:
            break
        if attempt < _MAX_REPLY_RETRIES:
            logger.warning(
                "[%s] reply too long (%d chars), retrying (attempt %d/%d)",
                request_id,
                len(reply),
                attempt + 1,
                _MAX_REPLY_RETRIES + 1,
            )
        else:
            logger.error(
                "[%s] reply still too long (%d chars) after %d retries, truncating",
                request_id,
                len(reply),
                _MAX_REPLY_RETRIES,
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
    _check_model_ready()

    request_id = uuid.uuid4().hex[:8]
    logger.info(
        "[%s] camichat message_len=%d",
        request_id,
        len(request.message),
    )

    current_mood = random.choice(CAMI_MOODS)
    logger.info("[%s] mood=%s", request_id, current_mood[:40])
    system_prompt = (
        get_cami_system_prompt()
        + _pronoun_suffix(request.pronoun, female_term="Mommy", male_term="Daddy")
        + f"\n\n[TODAY'S VIBE: {current_mood}]"
    )
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": request.message
                + _DISCORD_LENGTH_INSTRUCTION
                + _VERBOSITY_INSTRUCTIONS[request.verbosity],
            },
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
            "repeat_penalty": 1.2,
            "repeat_last_n": 256,
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
            logger.error(
                "[%s] Ollama returned status %d: %s",
                request_id,
                resp.status_code,
                resp.text,
            )
            raise HTTPException(status_code=500, detail="Inference error")

        data = resp.json()
        reply = data.get("message", {}).get("content", "[Model returned empty content]")

        if len(reply) <= DISCORD_MAX_LENGTH:
            break
        if attempt < _MAX_REPLY_RETRIES:
            logger.warning(
                "[%s] camichat reply too long (%d chars), retrying (attempt %d/%d)",
                request_id,
                len(reply),
                attempt + 1,
                _MAX_REPLY_RETRIES + 1,
            )
        else:
            logger.error(
                "[%s] camichat reply still too long (%d chars) after %d retries, truncating",
                request_id,
                len(reply),
                _MAX_REPLY_RETRIES,
            )
            reply = reply[:DISCORD_MAX_LENGTH]

    return {
        "request_id": request_id,
        "reply": reply,
    }


@app.post("/bonniebot")
async def bonniebot(request: BonnieChatRequest):
    """Send a message to the LLM via Ollama and return Bonnie's response."""
    if _http_client is None:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    _check_model_ready()

    request_id = uuid.uuid4().hex[:8]
    logger.info(
        "[%s] bonniebot level=%d message_len=%d",
        request_id,
        request.level,
        len(request.message),
    )

    current_mood = random.choice(BONNIE_MOODS)
    logger.info("[%s] mood=%s", request_id, current_mood[:40])
    system_prompt = (
        get_bonnie_system_prompt()
        + _pronoun_suffix(request.pronoun, female_term="Ma'am", male_term="Sir")
        + f"\n\n[TODAY'S VIBE: {current_mood}]"
    )
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": request.message
                + _DISCORD_LENGTH_INSTRUCTION
                + _VERBOSITY_INSTRUCTIONS[request.verbosity],
            },
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
            "repeat_penalty": 1.2,
            "repeat_last_n": 256,
        },
    }

    reply = "[Model returned empty content]"
    for attempt in range(_MAX_REPLY_RETRIES + 1):
        try:
            start = time.perf_counter()
            resp = await _http_client.post("/api/chat", json=ollama_payload)
            elapsed = time.perf_counter() - start
            logger.info("[%s] bonniebot inference completed in %.2f seconds", request_id, elapsed)
        except httpx.TimeoutException:
            logger.error("[%s] Ollama request timed out", request_id)
            raise HTTPException(status_code=504, detail="LLM inference timed out") from None
        except httpx.HTTPError as e:
            logger.error("[%s] Ollama request failed: %s", request_id, e)
            raise HTTPException(status_code=503, detail=f"Ollama not reachable: {e}") from None

        if resp.status_code != 200:
            logger.error(
                "[%s] Ollama returned status %d: %s",
                request_id,
                resp.status_code,
                resp.text,
            )
            raise HTTPException(status_code=500, detail="Inference error")

        data = resp.json()
        reply = data.get("message", {}).get("content", "[Model returned empty content]")

        if len(reply) <= DISCORD_MAX_LENGTH:
            break
        if attempt < _MAX_REPLY_RETRIES:
            logger.warning(
                "[%s] bonniebot reply too long (%d chars), retrying (attempt %d/%d)",
                request_id,
                len(reply),
                attempt + 1,
                _MAX_REPLY_RETRIES + 1,
            )
        else:
            logger.error(
                "[%s] bonniebot reply still too long (%d chars) after %d retries, truncating",
                request_id,
                len(reply),
                _MAX_REPLY_RETRIES,
            )
            reply = reply[:DISCORD_MAX_LENGTH]

    return {
        "request_id": request_id,
        "level": request.level,
        "reply": reply,
    }
