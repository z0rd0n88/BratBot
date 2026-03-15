"""Per-user and per-channel rate limiting using Redis fixed windows."""

from __future__ import annotations

import redis.asyncio as aioredis

from bratbot.config import settings
from bratbot.utils.logger import get_logger

log = get_logger(__name__)


class RateLimiter:
    """Redis-backed rate limiter using atomic INCR + EXPIRE (fixed window).

    Uses Redis pipelines to ensure INCR and EXPIRE execute atomically,
    preventing orphaned keys if the process crashes between the two commands.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def _check(self, key: str, window: int, max_requests: int) -> tuple[bool, int]:
        """Atomically increment and check a rate limit counter.

        Returns (allowed, count) where allowed is True if under the limit.
        """
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window)
            results = await pipe.execute()
            count = results[0]

        return count <= max_requests, count

    async def check_user(self, user_id: int, guild_id: int) -> bool:
        """Check if a user is within the per-user rate limit.

        Returns True if the request is allowed, False if rate-limited.
        Default: 1 interaction per `rate_limit_user_seconds` (5s).
        """
        key = f"ratelimit:user:{guild_id}:{user_id}"
        window = settings.rate_limit_user_seconds

        allowed, _count = await self._check(key, window, max_requests=1)
        if not allowed:
            ttl = await self.redis.ttl(key)
            log.debug(
                "rate_limit_user_hit",
                user_id=user_id,
                guild_id=guild_id,
                retry_after=ttl,
            )
        return allowed

    async def check_channel(self, channel_id: int) -> bool:
        """Check if a channel is within the per-channel rate limit.

        Returns True if the request is allowed, False if rate-limited.
        Default: max `rate_limit_channel_per_minute` (10) responses per 60s.
        """
        key = f"ratelimit:channel:{channel_id}"
        window = 60  # 1-minute fixed window
        max_requests = settings.rate_limit_channel_per_minute

        allowed, count = await self._check(key, window, max_requests)
        if not allowed:
            ttl = await self.redis.ttl(key)
            log.debug(
                "rate_limit_channel_hit",
                channel_id=channel_id,
                count=count,
                max=max_requests,
                retry_after=ttl,
            )
        return allowed
