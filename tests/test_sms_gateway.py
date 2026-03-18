"""Tests for the SMS gateway (sms/app.py)."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# sms/ is not a Python package — add to sys.path so `from settings import settings` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sms"))

import app as sms_app  # noqa: E402
from settings import settings as sms_settings  # noqa: E402

# Remove bare "app" and "settings" from sys.modules so they don't shadow
# model/app.py when test_verify.py runs in the same pytest session.
sys.modules.pop("app", None)
sys.modules.pop("settings", None)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TWILIO_FROM = "+15005550001"
TWILIO_TO = "+15005550006"
DEFAULT_BODY = "hey brat"
LLM_REPLY = "Whatever, I guess."


def _make_redis_mock(count: int = 1):
    """Build an async Redis mock whose pipeline returns *count* from INCR."""
    pipe = AsyncMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[count, True])

    redis = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=pipe)
    ctx.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=ctx)
    redis.ttl = AsyncMock(return_value=5)
    redis.aclose = AsyncMock()
    return redis


def _make_llm_transport(*, status: int = 200, reply: str = LLM_REPLY, raise_exc=None):
    """Build an httpx.MockTransport that returns a canned LLM response."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request):
        captured_requests.append(request)
        if raise_exc is not None:
            raise raise_exc
        return httpx.Response(status, json={"reply": reply})

    return httpx.MockTransport(handler), captured_requests


async def _post_incoming(client: httpx.AsyncClient, *, from_number=TWILIO_FROM, body=DEFAULT_BODY):
    """POST to /incoming with form-encoded Twilio webhook data."""
    data = {}
    if from_number is not None:
        data["From"] = from_number
    if body is not None:
        data["Body"] = body
    return await client.post("/incoming", data=data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sms_client(monkeypatch):
    """Fully configured SMS client — all mocks wired up, SMS enabled."""
    # Configure Twilio creds so _sms_configured() returns True
    monkeypatch.setattr(sms_settings, "twilio_account_sid", "ACtest123")
    monkeypatch.setattr(sms_settings, "twilio_auth_token", "test_auth_token")
    monkeypatch.setattr(sms_settings, "twilio_phone_number", TWILIO_TO)
    monkeypatch.setattr(sms_settings, "twilio_skip_validation", False)

    # Mock Twilio client
    twilio_mock = MagicMock()
    monkeypatch.setattr(sms_app, "_twilio_client", twilio_mock)

    # Mock validator — accept all signatures by default
    validator_mock = MagicMock()
    validator_mock.validate.return_value = True
    monkeypatch.setattr(sms_app, "_validator", validator_mock)

    # Mock Redis — first request allowed (count=1)
    redis_mock = _make_redis_mock(count=1)
    monkeypatch.setattr(sms_app, "_redis_client", redis_mock)

    # Mock HTTP client for LLM
    transport, captured = _make_llm_transport()
    http_client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
    monkeypatch.setattr(sms_app, "_http_client", http_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=sms_app.app),
        base_url="http://testserver",
    ) as client:
        yield client, twilio_mock, captured

    await http_client.aclose()


@pytest.fixture
async def unconfigured_sms_client(monkeypatch):
    """SMS client with Twilio creds unset — SMS disabled mode."""
    monkeypatch.setattr(sms_settings, "twilio_account_sid", None)
    monkeypatch.setattr(sms_settings, "twilio_auth_token", None)
    monkeypatch.setattr(sms_settings, "twilio_phone_number", None)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=sms_app.app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_sms_enabled(self, sms_client):
        client, _, _ = sms_client
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok", "sms_enabled": True}

    async def test_health_sms_disabled(self, unconfigured_sms_client):
        resp = await unconfigured_sms_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok", "sms_enabled": False}


# ---------------------------------------------------------------------------
# Incoming SMS — happy path
# ---------------------------------------------------------------------------


class TestIncomingHappyPath:
    async def test_incoming_returns_twiml(self, sms_client):
        client, _, _ = sms_client
        resp = await _post_incoming(client)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/xml")
        assert resp.text == "<Response/>"

    async def test_incoming_calls_llm(self, sms_client):
        client, _, captured = sms_client
        await _post_incoming(client, body="tell me something")
        assert len(captured) == 1
        payload = json.loads(captured[0].content)
        assert payload["message"] == "tell me something"
        assert payload["brat_level"] == sms_settings.llm_brat_level

    async def test_incoming_sends_sms_reply(self, sms_client):
        client, twilio_mock, _ = sms_client
        await _post_incoming(client)
        twilio_mock.messages.create.assert_called_once()
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert call_kwargs["to"] == TWILIO_FROM
        assert call_kwargs["from_"] == TWILIO_TO
        assert call_kwargs["body"] == LLM_REPLY


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    async def test_missing_from_returns_400(self, sms_client):
        client, _, _ = sms_client
        resp = await _post_incoming(client, from_number=None, body=DEFAULT_BODY)
        assert resp.status_code == 400

    async def test_empty_body_sends_empty_reply(self, sms_client):
        client, twilio_mock, _ = sms_client
        resp = await _post_incoming(client, body="")
        assert resp.status_code == 200
        assert resp.text == "<Response/>"
        twilio_mock.messages.create.assert_called_once()
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert call_kwargs["body"] == sms_app._EMPTY_MESSAGE_REPLY

    async def test_invalid_signature_returns_403(self, sms_client, monkeypatch):
        client, _, _ = sms_client
        # Override validator to reject
        monkeypatch.setattr(sms_app._validator, "validate", MagicMock(return_value=False))
        resp = await _post_incoming(client)
        assert resp.status_code == 403

    async def test_skip_validation_bypasses_check(self, sms_client, monkeypatch):
        client, _, _ = sms_client
        monkeypatch.setattr(sms_settings, "twilio_skip_validation", True)
        # Validator would reject, but skip_validation bypasses it
        monkeypatch.setattr(sms_app._validator, "validate", MagicMock(return_value=False))
        resp = await _post_incoming(client)
        assert resp.status_code == 200

    async def test_sms_disabled_returns_503(self, unconfigured_sms_client):
        resp = await _post_incoming(unconfigured_sms_client)
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    async def test_first_request_allowed(self, sms_client):
        """Redis count=1 (default) — request goes through to LLM."""
        client, twilio_mock, captured = sms_client
        await _post_incoming(client)
        assert len(captured) == 1  # LLM was called
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert call_kwargs["body"] == LLM_REPLY

    async def test_rate_limited_sends_reply(self, sms_client, monkeypatch):
        """Redis count=2 — rate limited, LLM not called."""
        client, twilio_mock, captured = sms_client
        monkeypatch.setattr(sms_app, "_redis_client", _make_redis_mock(count=2))
        await _post_incoming(client)
        assert len(captured) == 0  # LLM was NOT called
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert call_kwargs["body"] == sms_app._RATE_LIMITED_REPLY


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------


class TestLlmErrors:
    async def test_llm_timeout_sends_error_reply(self, monkeypatch, sms_client):
        client, twilio_mock, _ = sms_client
        transport, _ = _make_llm_transport(raise_exc=httpx.ReadTimeout("timed out"))
        http_client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
        monkeypatch.setattr(sms_app, "_http_client", http_client)

        await _post_incoming(client)
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert call_kwargs["body"] == sms_app._LLM_ERROR_REPLY
        await http_client.aclose()

    async def test_llm_500_sends_error_reply(self, monkeypatch, sms_client):
        client, twilio_mock, _ = sms_client
        transport, _ = _make_llm_transport(status=500, reply="")
        http_client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
        monkeypatch.setattr(sms_app, "_http_client", http_client)

        await _post_incoming(client)
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert call_kwargs["body"] == sms_app._LLM_ERROR_REPLY
        await http_client.aclose()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    async def test_long_message_truncated_to_llm(self, sms_client):
        """Messages > 2000 chars are truncated before sending to LLM."""
        client, _, captured = sms_client
        long_body = "x" * 3000
        await _post_incoming(client, body=long_body)
        assert len(captured) == 1
        payload = json.loads(captured[0].content)
        assert len(payload["message"]) == 2000

    async def test_sms_reply_truncated_to_1600(self, monkeypatch, sms_client):
        """LLM replies > 1600 chars are truncated before sending via Twilio."""
        client, twilio_mock, _ = sms_client
        long_reply = "y" * 2000
        transport, _ = _make_llm_transport(reply=long_reply)
        http_client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
        monkeypatch.setattr(sms_app, "_http_client", http_client)

        await _post_incoming(client)
        call_kwargs = twilio_mock.messages.create.call_args[1]
        assert len(call_kwargs["body"]) == 1600
        await http_client.aclose()
