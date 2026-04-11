"""Shared test fixtures for BratBot tests."""

import os
import sys
from pathlib import Path

import pytest

from common.services.llm_client import LLMClient

# ---------------------------------------------------------------------------
# Shared setup — runs before any test module is collected.
# DISCORD_PUBLIC_KEY must be set before model/verify.py is imported (it reads
# the env var at module level), and model/ must be on sys.path first.
# ---------------------------------------------------------------------------
from tests.discord_keys import verify_hex  # noqa: E402

os.environ["DISCORD_PUBLIC_KEY"] = verify_hex
os.environ.setdefault("TERMS_URL", "http://test")
os.environ.setdefault("PRIVACY_URL", "http://test")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("DISCORD_CLIENT_ID", "123456789")
os.environ.setdefault("LLM_API_URL", "http://test:8000")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
# Personality prompts: skip real decryption in tests so the model server's
# lifespan startup hook doesn't need a real PROMPTS_ENCRYPTION_KEY. The
# crypto path is tested in tests/test_prompt_loader.py with a fresh test key.
os.environ.setdefault("BRATBOT_TEST_MODE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_client() -> LLMClient:
    """LLMClient with test defaults — no real server needed."""
    return LLMClient(
        base_url="http://test:8000",
        chat_endpoint="/bratchat",
        timeout=10.0,
    )


@pytest.fixture
async def redis_mock():
    """Mock Redis client for testing — in-memory storage."""

    class MockRedis:
        def __init__(self):
            self._store: dict = {}

        async def set(self, key: str, value: str) -> None:
            self._store[key] = value

        async def get(self, key: str) -> str | None:
            return self._store.get(key)

        async def delete(self, key: str) -> None:
            self._store.pop(key, None)

        async def exists(self, key: str) -> bool:
            return key in self._store

    return MockRedis()
