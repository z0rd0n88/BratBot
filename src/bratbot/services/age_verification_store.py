"""Service for storing and retrieving user age verification status from Redis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class AgeVerificationStore:
    """Manages per-user age verification status in Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def is_verified(self, user_id: int) -> bool:
        """Check if user has completed age verification."""
        key = f"user:{user_id}:age_verified"
        return bool(await self.redis.exists(key))

    async def set_verified(self, user_id: int) -> None:
        """Mark user as age-verified (permanent, no expiry)."""
        key = f"user:{user_id}:age_verified"
        await self.redis.set(key, "1")
