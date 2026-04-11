"""Tests for ConversationHistoryStore."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.services.conversation_history import ALL_PERSONA_NAMES, ConversationHistoryStore


# ---------------------------------------------------------------------------
# Mock Redis with list support
# ---------------------------------------------------------------------------


class MockPipeline:
    """Fake Redis pipeline that queues rpush/ltrim, then applies on execute()."""

    def __init__(self, store: dict) -> None:
        self._store = store
        self._ops: list = []

    def rpush(self, key: str, value: str) -> None:
        self._ops.append(("rpush", key, value))

    def ltrim(self, key: str, start: int, end: int) -> None:
        self._ops.append(("ltrim", key, start, end))

    async def execute(self) -> list:
        for op in self._ops:
            if op[0] == "rpush":
                _, key, value = op
                self._store.setdefault(key, []).append(value)
            elif op[0] == "ltrim":
                _, key, start, end = op
                lst = self._store.get(key, [])
                # Redis ltrim(key, start, end) keeps [start:end+1] counting from left,
                # but negative indices count from the right (e.g. -20 = max(-20, 0)).
                length = len(lst)
                if start < 0:
                    start = max(0, length + start)
                if end < 0:
                    end = length + end
                self._store[key] = lst[start : end + 1]
        return [None] * len(self._ops)


class MockRedis:
    """In-memory Redis mock supporting list and delete operations."""

    def __init__(self) -> None:
        self._store: dict[str, list[str]] = {}

    async def lrange(self, key: str, start: int, end: int) -> list[bytes]:
        lst = self._store.get(key, [])
        if end == -1:
            end = len(lst)
        else:
            end = end + 1
        return [item.encode() if isinstance(item, str) else item for item in lst[start:end]]

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted

    def pipeline(self) -> MockPipeline:
        return MockPipeline(self._store)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis() -> MockRedis:
    return MockRedis()


@pytest.fixture
def store(redis: MockRedis) -> ConversationHistoryStore:
    return ConversationHistoryStore(redis, "bratbot", history_size=3)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConversationHistoryStore:
    async def test_get_empty(self, store: ConversationHistoryStore) -> None:
        """Returns empty list when no history exists."""
        result = await store.get(channel_id=1, user_id=42)
        assert result == []

    async def test_append_and_get(self, store: ConversationHistoryStore) -> None:
        """Messages are stored and retrieved in order."""
        await store.append(1, 42, "hello", "hi there")
        history = await store.get(1, 42)
        assert history == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

    async def test_multiple_exchanges_in_order(self, store: ConversationHistoryStore) -> None:
        """Multiple exchanges are returned oldest-first."""
        await store.append(1, 42, "first", "reply1")
        await store.append(1, 42, "second", "reply2")
        history = await store.get(1, 42)
        assert history[0] == {"role": "user", "content": "first"}
        assert history[1] == {"role": "assistant", "content": "reply1"}
        assert history[2] == {"role": "user", "content": "second"}
        assert history[3] == {"role": "assistant", "content": "reply2"}

    async def test_trim_to_window(self, store: ConversationHistoryStore) -> None:
        """List stays bounded at history_size * 2 entries (store has history_size=3)."""
        # 4 exchanges = 8 entries; window is 3*2=6 so oldest 2 should be trimmed
        for i in range(4):
            await store.append(1, 42, f"msg{i}", f"reply{i}")
        history = await store.get(1, 42)
        assert len(history) == 6
        # Oldest exchange (msg0/reply0) should be gone
        assert history[0]["content"] == "msg1"

    async def test_clear(self, store: ConversationHistoryStore) -> None:
        """clear() deletes this persona's history for the given channel/user."""
        await store.append(1, 42, "hello", "hi")
        await store.clear(1, 42)
        result = await store.get(1, 42)
        assert result == []

    async def test_clear_all(self, redis: MockRedis) -> None:
        """clear_all() deletes history for every persona."""
        # Populate history for all three personas manually
        for persona in ALL_PERSONA_NAMES:
            s = ConversationHistoryStore(redis, persona, history_size=5)
            await s.append(1, 42, "msg", "reply")

        # Verify they all exist
        for persona in ALL_PERSONA_NAMES:
            s = ConversationHistoryStore(redis, persona, history_size=5)
            assert await s.get(1, 42) != []

        # clear_all via any store (uses the shared constant)
        any_store = ConversationHistoryStore(redis, "bratbot", history_size=5)
        await any_store.clear_all(1, 42)

        for persona in ALL_PERSONA_NAMES:
            s = ConversationHistoryStore(redis, persona, history_size=5)
            assert await s.get(1, 42) == []

    async def test_different_channels_independent(self, store: ConversationHistoryStore) -> None:
        """History is keyed per channel — different channels don't bleed."""
        await store.append(channel_id=10, user_id=42, user_msg="ch10", bot_reply="r10")
        await store.append(channel_id=20, user_id=42, user_msg="ch20", bot_reply="r20")
        assert (await store.get(10, 42))[0]["content"] == "ch10"
        assert (await store.get(20, 42))[0]["content"] == "ch20"

    async def test_different_users_independent(self, store: ConversationHistoryStore) -> None:
        """History is keyed per user — different users don't bleed."""
        await store.append(1, user_id=100, user_msg="user100", bot_reply="r100")
        await store.append(1, user_id=200, user_msg="user200", bot_reply="r200")
        assert (await store.get(1, 100))[0]["content"] == "user100"
        assert (await store.get(1, 200))[0]["content"] == "user200"

    async def test_redis_failure_degrades_gracefully(self) -> None:
        """A Redis error on get() raises, letting the caller handle it gracefully."""
        broken_redis = MagicMock()
        broken_redis.lrange = AsyncMock(side_effect=ConnectionError("Redis down"))
        store = ConversationHistoryStore(broken_redis, "bratbot")

        with pytest.raises(ConnectionError):
            await store.get(1, 42)
