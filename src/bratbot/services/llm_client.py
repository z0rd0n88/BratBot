"""Async HTTP client for the custom LLM server API."""

from __future__ import annotations

import httpx

from bratbot.utils.logger import get_logger

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
    """Wraps the LLM server's ``/health``, chat, and ``/camichat`` endpoints.

    Args:
        base_url: Base URL of the model server.
        chat_endpoint: Path called by :meth:`chat` (e.g. ``"/bratchat"`` or ``"/bonniebot"``).
        default_brat_level: Default intensity level when none is supplied.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        chat_endpoint: str,
        default_brat_level: int,
        timeout: float,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )
        self._chat_endpoint = chat_endpoint
        self._default_brat_level = default_brat_level

    async def health_check(self) -> bool:
        """Return ``True`` if the LLM server is healthy (model loaded)."""
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat(self, message: str, brat_level: int | None = None, verbosity: int = 2) -> dict:
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
        payload = {
            "message": message[:2000],
            "brat_level": brat_level if brat_level is not None else self._default_brat_level,
            "verbosity": verbosity,
        }

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
            brat_level=data.get("brat_level"),
        )
        return data

    async def cami_chat(self, message: str, verbosity: int = 2) -> dict:
        """Send a message to the Cami personality endpoint.

        Returns:
            ``{"request_id": ..., "reply": ...}``

        Raises:
            LLMConnectionError: Server unreachable.
            LLMTimeoutError: Request timed out.
            LLMServerError: 5xx response.
            LLMValidationError: 4xx response.
        """
        payload = {"message": message[:2000], "verbosity": verbosity}

        try:
            resp = await self._client.post("/camichat", json=payload)
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
        log.debug("llm_cami_chat_response", request_id=data.get("request_id"))
        return data

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
