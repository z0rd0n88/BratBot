"""Shared test fixtures for BratBot tests."""

import os
import sys
from pathlib import Path

import pytest

from bratbot.services.llm_client import LLMClient

# ---------------------------------------------------------------------------
# Shared setup — runs before any test module is collected.
# DISCORD_PUBLIC_KEY must be set before model/verify.py is imported (it reads
# the env var at module level), and model/ must be on sys.path first.
# ---------------------------------------------------------------------------
from tests.discord_keys import verify_hex  # noqa: E402

os.environ["DISCORD_PUBLIC_KEY"] = verify_hex

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_client() -> LLMClient:
    """LLMClient with test defaults — no real server needed."""
    return LLMClient(
        base_url="http://test:8000",
        default_brat_level=3,
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
