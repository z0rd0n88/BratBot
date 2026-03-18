"""Tests for Discord request signature verification and interactions endpoint."""

import json
import os
import sys
from pathlib import Path

import pytest
from nacl.signing import SigningKey

# Generate a test keypair — the private key signs, the public key verifies
_signing_key = SigningKey.generate()
_verify_hex = _signing_key.verify_key.encode().hex()

# Patch env before importing the modules under test
os.environ["DISCORD_PUBLIC_KEY"] = _verify_hex

# Add model/ to sys.path so its modules are importable (it's not a package)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))

from starlette.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def _sign(timestamp: str, body: str) -> str:
    """Sign a Discord-style message and return the hex signature."""
    message = f"{timestamp}{body}".encode()
    signed = _signing_key.sign(message)
    # signed.signature is the 64-byte Ed25519 signature
    return signed.signature.hex()


class TestSignatureVerification:
    def test_valid_signature_ping(self, client):
        body = json.dumps({"type": 1})
        timestamp = "1234567890"
        signature = _sign(timestamp, body)

        resp = client.post(
            "/interactions",
            content=body,
            headers={
                "X-Signature-Ed25519": signature,
                "X-Signature-Timestamp": timestamp,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"type": 1}

    def test_invalid_signature_returns_401(self, client):
        body = json.dumps({"type": 1})
        timestamp = "1234567890"
        # Sign with correct body, then tamper
        signature = _sign(timestamp, body)
        tampered_body = json.dumps({"type": 1, "extra": "tampered"})

        resp = client.post(
            "/interactions",
            content=tampered_body,
            headers={
                "X-Signature-Ed25519": signature,
                "X-Signature-Timestamp": timestamp,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_missing_signature_header_returns_401(self, client):
        body = json.dumps({"type": 1})
        resp = client.post(
            "/interactions",
            content=body,
            headers={
                "X-Signature-Timestamp": "1234567890",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_missing_timestamp_header_returns_401(self, client):
        body = json.dumps({"type": 1})
        signature = _sign("1234567890", body)
        resp = client.post(
            "/interactions",
            content=body,
            headers={
                "X-Signature-Ed25519": signature,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_malformed_signature_returns_401(self, client):
        body = json.dumps({"type": 1})
        resp = client.post(
            "/interactions",
            content=body,
            headers={
                "X-Signature-Ed25519": "not-valid-hex",
                "X-Signature-Timestamp": "1234567890",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_application_command_returns_deferred(self, client):
        body = json.dumps({"type": 2, "id": "test-cmd-123"})
        timestamp = "1234567890"
        signature = _sign(timestamp, body)

        resp = client.post(
            "/interactions",
            content=body,
            headers={
                "X-Signature-Ed25519": signature,
                "X-Signature-Timestamp": timestamp,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"type": 5}


class TestInternalEndpointsUnaffected:
    """Verify that /health and /bratchat don't require Discord signatures."""

    def test_health_no_signature_needed(self, client):
        resp = client.get("/health")
        # May return 503 if Ollama isn't running, but NOT 401
        assert resp.status_code != 401
