"""Tests for the model API — ChatRequest validation and /bratchat endpoint."""

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

# conftest.py sets DISCORD_PUBLIC_KEY and adds model/ to sys.path before collection
from app import BonnieChatRequest, CamiChatRequest, ChatRequest, app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# ChatRequest model validation
# ---------------------------------------------------------------------------


class TestChatRequestMessageValidation:
    @pytest.mark.parametrize(
        "message",
        [
            "what's up",  # apostrophe
            'say "hello" to me',  # double quotes
            "back\\slash",  # backslash
            "line1\nline2",  # newline
            "tab\there",  # tab
            "100% done & dusted",  # percent + ampersand
            "<script>alert('xss')</script>",  # angle brackets
            "emoji 🎉 and kanji こんにちは",  # mixed unicode
        ],
    )
    def test_accepts_special_characters(self, message):
        """ChatRequest must accept any valid string content without validation errors."""
        req = ChatRequest(message=message)
        assert req.message == message

    def test_rejects_empty_message(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="")


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


class TestCamiChatRequestPronoun:
    def test_pronoun_defaults_to_male(self):
        req = CamiChatRequest(message="hi")
        assert req.pronoun == "male"

    def test_pronoun_female(self):
        req = CamiChatRequest(message="hi", pronoun="female")
        assert req.pronoun == "female"

    def test_pronoun_other(self):
        req = CamiChatRequest(message="hi", pronoun="other")
        assert req.pronoun == "other"


class TestBonnieChatRequestPronoun:
    def test_pronoun_defaults_to_male(self):
        req = BonnieChatRequest(message="hi")
        assert req.pronoun == "male"

    def test_pronoun_female(self):
        req = BonnieChatRequest(message="hi", pronoun="female")
        assert req.pronoun == "female"

    def test_pronoun_other(self):
        req = BonnieChatRequest(message="hi", pronoun="other")
        assert req.pronoun == "other"


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

    @pytest.mark.parametrize(
        "message",
        [
            "what's up",  # apostrophe
            'say "hello" to me',  # double quotes
            "back\\slash",  # backslash
            "line1\nline2",  # newline
            "<script>alert('xss')</script>",  # angle brackets
            "emoji 🎉 こんにちは",  # unicode
        ],
    )
    def test_accepts_special_characters_in_request(self, client, message):
        """Special characters must not cause a 422 validation error."""
        resp = client.post("/bratchat", json={"message": message})
        assert resp.status_code != 422
