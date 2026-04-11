"""Async HTTP client for the custom LLM server API."""

from __future__ import annotations

import httpx

from common.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMConnectionError(LLMError):
    """Server unreachable or connection failed."""


class LLMTimeoutError(LLMError):
    """Request timed out."""


class LLMServerError(LLMError):
    """Server returned a 5xx response."""


class LLMValidationError(LLMError):
    """Server returned a 4xx response (bad request)."""


class LLMWarmingError(LLMError):
    """Server is still loading the model into VRAM."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    """Wraps the LLM server's ``/health`` and chat endpoints.

    Args:
        base_url: Base URL of the model server.
        chat_endpoint: Path called by :meth:`chat` (e.g. ``"/bratchat"``, ``"/camichat"``, ``"/bonniebot"``).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        chat_endpoint: str,
        timeout: float,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )
        self._chat_endpoint = chat_endpoint

    async def health_check(self) -> bool:
        """Return ``True`` if the LLM server is healthy (model loaded)."""
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat(
        self,
        message: str,
        *,
        verbosity: int = 2,
        pronoun: str = "male",
        history: list[dict] | None = None,
    ) -> dict:
        """Send a message and return the server's response dict.

        Posts to the ``chat_endpoint`` supplied at construction time.

        Returns:
            ``{"request_id": ..., "reply": ...}``

        Raises:
            LLMConnectionError: Server unreachable.
            LLMTimeoutError: Request timed out.
            LLMServerError: 5xx response.
            LLMValidationError: 4xx response.
        """
        payload: dict = {
            "message": message[:2000],
            "verbosity": verbosity,
            "history": history or [],
        }
        if pronoun != "male":
            payload["pronoun"] = pronoun

        try:
            resp = await self._client.post(self._chat_endpoint, json=payload)
        except httpx.ConnectError as exc:
            raise LLMConnectionError("LLM server unreachable") from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError(str(exc)) from exc

        if resp.status_code == 503:
            try:
                detail = resp.json().get("detail")
                if isinstance(detail, dict) and detail.get("status") == "warming_up":
                    raise LLMWarmingError("Model is warming up")
            except (ValueError, AttributeError):
                pass
        if resp.status_code >= 500:
            raise LLMServerError(f"LLM server error: {resp.status_code}")
        if resp.status_code >= 400:
            raise LLMValidationError(f"LLM bad request: {resp.status_code}")

        data = resp.json()
        log.debug(
            "llm_chat_response",
            request_id=data.get("request_id"),
        )
        return data

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
