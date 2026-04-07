"""Service for storing and retrieving user verbosity settings from Redis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class VerbosityStore:
    """Manages per-user verbosity settings in Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def set_verbosity(self, user_id: int, verbosity: int) -> None:
        """Set user's preferred verbosity level (1-3).

        Args:
            user_id: Discord user ID
            verbosity: Response length level (1=short, 2=medium, 3=long)

        Raises:
            ValueError: If verbosity is not in range [1, 3]
        """
        if not (1 <= verbosity <= 3):
            raise ValueError("verbosity must be between 1 and 3")
        await self.redis.set(f"user:{user_id}:verbosity", str(verbosity))

    async def get_verbosity(self, user_id: int) -> int:
        """Get user's preferred verbosity level.

        Args:
            user_id: Discord user ID

        Returns:
            Verbosity level (1-3), defaults to 2 if not set
        """
        value = await self.redis.get(f"user:{user_id}:verbosity")
        return int(value) if value is not None else 2

    async def was_set(self, user_id: int) -> bool:
        """Check if user has explicitly set their verbosity preference."""
        return await self.redis.exists(f"user:{user_id}:verbosity")
