"""Service for storing and retrieving user brat intensity settings from Redis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class IntensityStore:
    """Manages per-user brat intensity settings in Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def set_intensity(self, user_id: int, intensity: int) -> None:
        """Set user's preferred brat intensity level (1-3).

        Args:
            user_id: Discord user ID
            intensity: Brat level (1-3)

        Raises:
            ValueError: If intensity is not in range [1, 3]
        """
        if not (1 <= intensity <= 3):
            raise ValueError("intensity must be between 1 and 3")

        key = f"user:{user_id}:intensity"
        await self.redis.set(key, str(intensity))

    async def get_intensity(self, user_id: int) -> int:
        """Get user's preferred brat intensity level.

        Args:
            user_id: Discord user ID

        Returns:
            Intensity level (1-3), defaults to 3 if not set
        """
        key = f"user:{user_id}:intensity"
        value = await self.redis.get(key)
        return int(value) if value is not None else 3

    async def was_set(self, user_id: int) -> bool:
        """Check if user has explicitly set their intensity preference.

        Args:
            user_id: Discord user ID

        Returns:
            True if user has set a preference, False otherwise
        """
        key = f"user:{user_id}:intensity"
        return bool(await self.redis.exists(key))
