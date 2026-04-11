import redis.asyncio as aioredis

_redis_client: aioredis.Redis | None = None


async def get_redis(url: str | None = None) -> aioredis.Redis:
    """Get or create the async Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        if url is None:
            from bratbot.config import settings

            url = settings.redis_url
        _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
