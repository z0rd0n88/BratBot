"""Service for storing and retrieving user pronoun preferences from Redis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis

_VALID_PRONOUNS = {"male", "female", "other"}


class PronounStore:
    """Manages per-user pronoun preferences in Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def set_pronoun(self, user_id: int, pronoun: str) -> None:
        """Set user's pronoun preference.

        Args:
            user_id: Discord user ID
            pronoun: One of "male", "female", "other"

        Raises:
            ValueError: If pronoun is not a valid value
        """
        if pronoun not in _VALID_PRONOUNS:
            raise ValueError(f"pronoun must be one of {sorted(_VALID_PRONOUNS)}, got {pronoun!r}")
        await self.redis.set(f"user:{user_id}:pronoun", pronoun)

    async def get_pronoun(self, user_id: int) -> str:
        """Get user's pronoun preference.

        Args:
            user_id: Discord user ID

        Returns:
            Pronoun preference ("male", "female", or "other"), defaults to "male" if not set
        """
        value = await self.redis.get(f"user:{user_id}:pronoun")
        return value if value is not None else "male"

    async def was_set(self, user_id: int) -> bool:
        """Check if user has explicitly set their pronoun preference."""
        return bool(await self.redis.exists(f"user:{user_id}:pronoun"))
