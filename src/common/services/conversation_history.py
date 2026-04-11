"""Per-user, per-channel, per-persona conversation history stored in Redis."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = logging.getLogger(__name__)

ALL_PERSONA_NAMES = ["bratbot", "cami", "bonniebot"]


class ConversationHistoryStore:
    """Stores sliding-window conversation history in a Redis list.

    Key pattern: ``history:{persona}:channel:{channel_id}:{user_id}``
    Each entry is a JSON-encoded ``{"role": "user"|"assistant", "content": "..."}`` dict.
    The list is trimmed to ``history_size * 2`` entries on every write.
    """

    def __init__(self, redis: aioredis.Redis, persona: str, history_size: int = 10) -> None:
        self._redis = redis
        self._persona = persona
        self._history_size = history_size

    def _key(self, channel_id: int, user_id: int) -> str:
        return f"history:{self._persona}:channel:{channel_id}:{user_id}"

    async def get(self, channel_id: int, user_id: int) -> list[dict]:
        """Return conversation history as a list of role/content dicts, oldest first."""
        raw = await self._redis.lrange(self._key(channel_id, user_id), 0, -1)
        result = []
        for m in raw:
            try:
                result.append(json.loads(m))
            except (json.JSONDecodeError, TypeError):
                log.warning("skipping corrupt history entry for %s", self._key(channel_id, user_id))
        return result

    async def append(self, channel_id: int, user_id: int, user_msg: str, bot_reply: str) -> None:
        """Push one exchange (user + assistant turn) and trim to the sliding window."""
        key = self._key(channel_id, user_id)
        pipe = self._redis.pipeline()
        pipe.rpush(key, json.dumps({"role": "user", "content": user_msg}))
        pipe.rpush(key, json.dumps({"role": "assistant", "content": bot_reply}))
        pipe.ltrim(key, -(self._history_size * 2), -1)
        await pipe.execute()

    async def clear(self, channel_id: int, user_id: int) -> None:
        """Delete this persona's history for the given channel/user pair."""
        await self._redis.delete(self._key(channel_id, user_id))

    async def clear_all(self, channel_id: int, user_id: int) -> None:
        """Delete history for all personas for the given channel/user pair."""
        keys = [f"history:{name}:channel:{channel_id}:{user_id}" for name in ALL_PERSONA_NAMES]
        await self._redis.delete(*keys)
