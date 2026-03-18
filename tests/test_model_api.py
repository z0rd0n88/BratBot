"""Tests for the model API — ChatRequest validation and /bratchat endpoint."""

import pytest

# conftest.py sets DISCORD_PUBLIC_KEY and adds model/ to sys.path before collection
from app import ChatRequest, app
from pydantic import ValidationError
from starlette.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# ChatRequest model validation
# ---------------------------------------------------------------------------


class TestChatRequestBratLevel:
    def test_brat_level_defaults_to_3(self):
        req = ChatRequest(message="hi")
        assert req.brat_level == 3

    def test_brat_level_explicit_override(self):
        req = ChatRequest(message="hi", brat_level=1)
        assert req.brat_level == 1

    @pytest.mark.parametrize("level", [1, 2, 3])
    def test_brat_level_accepts_valid_range(self, level: int):
        req = ChatRequest(message="hi", brat_level=level)
        assert req.brat_level == level

    @pytest.mark.parametrize("level", [0, -1, 4, 100])
    def test_brat_level_rejects_out_of_range(self, level: int):
        with pytest.raises(ValidationError):
            ChatRequest(message="hi", brat_level=level)

    def test_brat_level_rejects_non_int(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="hi", brat_level="high")


# ---------------------------------------------------------------------------
# /bratchat endpoint — request validation layer
# ---------------------------------------------------------------------------


class TestBratchatRequestValidation:
    def test_accepts_request_without_brat_level(self, client):
        """Omitting brat_level should not cause a 422 validation error."""
        resp = client.post("/bratchat", json={"message": "hi"})
        assert resp.status_code != 422

    def test_accepts_request_with_brat_level(self, client):
        resp = client.post("/bratchat", json={"message": "hi", "brat_level": 2})
        assert resp.status_code != 422

    def test_rejects_invalid_brat_level(self, client):
        resp = client.post("/bratchat", json={"message": "hi", "brat_level": 5})
        assert resp.status_code == 422

    def test_rejects_missing_message(self, client):
        resp = client.post("/bratchat", json={"brat_level": 2})
        assert resp.status_code == 422
