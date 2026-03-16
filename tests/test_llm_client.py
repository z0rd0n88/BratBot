"""Tests for the LLM client — verifies request formation, response handling, and error mapping."""

from __future__ import annotations

import json

import httpx
import pytest

from bratbot.services.llm_client import (
    LLMClient,
    LLMConnectionError,
    LLMServerError,
    LLMTimeoutError,
    LLMValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHAT_RESPONSE = {
    "request_id": "abc123",
    "brat_level": 3,
    "reply": "Oh, you want ME to explain this? Fine.",
}


def _inject_transport(client: LLMClient, handler) -> None:
    """Replace the client's internal httpx transport with a mock handler."""
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test:8000",
    )


def _ok_chat_handler(request: httpx.Request) -> httpx.Response:
    """Default handler that returns a successful chat response."""
    return httpx.Response(200, json=CHAT_RESPONSE)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthCheck:
    async def test_health_check_ok(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/health"
            return httpx.Response(200, json={"status": "ok"})

        _inject_transport(llm_client, handler)
        assert await llm_client.health_check() is True

    async def test_health_check_model_not_loaded(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        _inject_transport(llm_client, handler)
        assert await llm_client.health_check() is False

    async def test_health_check_server_unreachable(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        _inject_transport(llm_client, handler)
        assert await llm_client.health_check() is False

    async def test_health_check_timeout(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Read timed out")

        _inject_transport(llm_client, handler)
        assert await llm_client.health_check() is False


# ---------------------------------------------------------------------------
# POST /chat — happy path
# ---------------------------------------------------------------------------


class TestChatHappyPath:
    async def test_chat_basic(self, llm_client: LLMClient) -> None:
        _inject_transport(llm_client, _ok_chat_handler)

        result = await llm_client.chat("Hello")

        assert result["request_id"] == "abc123"
        assert result["brat_level"] == 3
        assert "explain" in result["reply"].lower()

    async def test_chat_sends_correct_payload(self, llm_client: LLMClient) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        await llm_client.chat("test msg", brat_level=4)

        assert captured["method"] == "POST"
        assert captured["path"] == "/chat"
        assert captured["body"] == {"message": "test msg", "brat_level": 4}

    async def test_chat_uses_default_brat_level(self, llm_client: LLMClient) -> None:
        """When no brat_level is passed, the client's default (3) is used."""
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        await llm_client.chat("hi")

        assert captured["body"]["brat_level"] == 3

    async def test_chat_explicit_brat_level_overrides_default(self, llm_client: LLMClient) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        await llm_client.chat("hi", brat_level=1)

        assert captured["body"]["brat_level"] == 1

    @pytest.mark.parametrize("brat_level", [1, 2, 3, 4, 5])
    async def test_chat_each_brat_level(self, llm_client: LLMClient, brat_level: int) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={**CHAT_RESPONSE, "brat_level": brat_level},
            )

        _inject_transport(llm_client, handler)
        result = await llm_client.chat("test", brat_level=brat_level)

        assert captured["body"]["brat_level"] == brat_level
        assert result["brat_level"] == brat_level


# ---------------------------------------------------------------------------
# POST /chat — message edge cases (server accepts 1–2000 chars)
# ---------------------------------------------------------------------------


class TestChatMessageEdgeCases:
    async def test_chat_truncates_at_2000_chars(self, llm_client: LLMClient) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        long_message = "x" * 3000
        await llm_client.chat(long_message)

        assert len(captured["body"]["message"]) == 2000

    async def test_chat_single_char_message(self, llm_client: LLMClient) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        await llm_client.chat("a")

        assert captured["body"]["message"] == "a"

    async def test_chat_exactly_2000_chars(self, llm_client: LLMClient) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        exact_message = "y" * 2000
        await llm_client.chat(exact_message)

        assert len(captured["body"]["message"]) == 2000
        assert captured["body"]["message"] == exact_message

    async def test_chat_unicode_message(self, llm_client: LLMClient) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=CHAT_RESPONSE)

        _inject_transport(llm_client, handler)
        unicode_msg = "Hello 🌍 你好 مرحبا"
        await llm_client.chat(unicode_msg)

        assert captured["body"]["message"] == unicode_msg


# ---------------------------------------------------------------------------
# POST /chat — error responses
# ---------------------------------------------------------------------------


class TestChatErrors:
    async def test_chat_422_invalid_input(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": "Invalid input"})

        _inject_transport(llm_client, handler)

        with pytest.raises(LLMValidationError, match="422"):
            await llm_client.chat("")

    async def test_chat_503_model_not_loaded(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        _inject_transport(llm_client, handler)

        with pytest.raises(LLMServerError, match="503"):
            await llm_client.chat("hello")

    async def test_chat_500_internal_error(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        _inject_transport(llm_client, handler)

        with pytest.raises(LLMServerError, match="500"):
            await llm_client.chat("hello")

    async def test_chat_server_unreachable(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        _inject_transport(llm_client, handler)

        with pytest.raises(LLMConnectionError, match="unreachable"):
            await llm_client.chat("hello")

    async def test_chat_timeout(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Read timed out")

        _inject_transport(llm_client, handler)

        with pytest.raises(LLMTimeoutError, match="timed out"):
            await llm_client.chat("hello")

    async def test_chat_generic_http_error(self, llm_client: LLMClient) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.HTTPError("Something unexpected")

        _inject_transport(llm_client, handler)

        with pytest.raises(LLMConnectionError):
            await llm_client.chat("hello")


# ---------------------------------------------------------------------------
# Client lifecycle
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    async def test_close(self, llm_client: LLMClient) -> None:
        _inject_transport(llm_client, _ok_chat_handler)

        # Verify client works before close
        result = await llm_client.chat("test")
        assert result["request_id"] == "abc123"

        # Close and verify
        await llm_client.close()
        assert llm_client._client.is_closed
