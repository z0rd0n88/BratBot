"""Per-channel LLM request queue to prevent overlapping responses."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any

import discord

from bratbot.config import settings
from bratbot.utils.logger import get_logger

log = get_logger(__name__)

# In-character messages for queue states
QUEUE_FULL_MESSAGE = "I literally can't keep up with all of you right now. Chill."
TIMEOUT_MESSAGE = "I lost my train of thought. Try again, I guess."


class RequestQueue:
    """Manages per-channel async queues for serialized LLM request processing.

    Each channel gets its own queue + worker task to ensure only one LLM call
    runs at a time per channel. This prevents overlapping responses and
    respects rate limits.
    """

    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue] = defaultdict(
            lambda: asyncio.Queue(maxsize=settings.llm_queue_max_depth)
        )
        self._workers: dict[int, asyncio.Task] = {}

    async def enqueue(
        self,
        channel: discord.abc.Messageable,
        coro: Coroutine[Any, Any, Any],
    ) -> bool:
        """Add an LLM request to the channel's queue.

        Args:
            channel: The Discord channel to process the request in.
            coro: The coroutine to execute (typically an LLM call).

        Returns:
            True if enqueued successfully, False if the queue is full.
        """
        channel_id = channel.id  # type: ignore[union-attr]
        queue = self._queues[channel_id]

        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        try:
            queue.put_nowait((coro, future, channel))
        except asyncio.QueueFull:
            log.warning(
                "queue_full",
                channel_id=channel_id,
                depth=settings.llm_queue_max_depth,
            )
            await channel.send(QUEUE_FULL_MESSAGE)
            return False

        # Ensure a worker exists for this channel
        if channel_id not in self._workers or self._workers[channel_id].done():
            self._workers[channel_id] = asyncio.create_task(self._process_queue(channel_id))

        # Wait for our specific request to complete
        try:
            await future
        except Exception:
            # Error handling is done in the worker; just propagate
            raise

        return True

    async def _process_queue(self, channel_id: int) -> None:
        """Worker loop: process queued LLM requests one at a time."""
        queue = self._queues[channel_id]

        while not queue.empty():
            coro, future, channel = await queue.get()

            try:
                # Show typing indicator while processing (skip for DMs — they already show "thinking" from defer)
                if isinstance(channel, discord.DMChannel):
                    result = await asyncio.wait_for(
                        coro,
                        timeout=settings.llm_timeout_seconds,
                    )
                else:
                    async with channel.typing():
                        result = await asyncio.wait_for(
                            coro,
                            timeout=settings.llm_timeout_seconds,
                        )
                future.set_result(result)

            except TimeoutError:
                log.error(
                    "llm_timeout",
                    channel_id=channel_id,
                    timeout=settings.llm_timeout_seconds,
                )
                await channel.send(TIMEOUT_MESSAGE)
                if not future.done():
                    future.set_exception(TimeoutError("LLM request timed out"))

            except Exception as e:
                log.error(
                    "llm_request_failed",
                    channel_id=channel_id,
                    error=str(e),
                )
                if not future.done():
                    future.set_exception(e)

            finally:
                queue.task_done()

        # Clean up when queue is drained
        self._workers.pop(channel_id, None)
        self._queues.pop(channel_id, None)
