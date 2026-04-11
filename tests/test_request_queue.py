"""Tests for RequestQueue behavior with DM and guild channels."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from common.services.request_queue import RequestQueue


@pytest.fixture
def request_queue() -> RequestQueue:
    """Create a fresh RequestQueue for each test."""
    return RequestQueue()


@pytest.mark.asyncio
async def test_dm_channel_skips_typing(request_queue: RequestQueue) -> None:
    """DM channels should not attempt to use channel.typing()."""
    # Create a mock DM channel
    dm_channel = AsyncMock(spec=discord.DMChannel)
    dm_channel.id = 12345
    dm_channel.send = AsyncMock()

    # Create a simple coroutine that returns a result
    async def test_coro():
        return "test_result"

    # Enqueue the request
    await request_queue.enqueue(dm_channel, test_coro())

    # Verify typing was not called — DM channels skip the typing indicator
    assert dm_channel.typing.call_count == 0, "typing() should not be called for DM channels"


@pytest.mark.asyncio
async def test_guild_channel_uses_typing(request_queue: RequestQueue) -> None:
    """Guild channels should use channel.typing()."""
    # Create a mock guild channel
    guild_channel = AsyncMock(spec=discord.TextChannel)
    guild_channel.id = 12345
    guild_channel.send = AsyncMock()

    # Track if typing() was called
    typing_called = False

    class AsyncTypingContext:
        async def __aenter__(self):
            nonlocal typing_called
            typing_called = True
            return self

        async def __aexit__(self, *args):
            pass

    guild_channel.typing = MagicMock(return_value=AsyncTypingContext())

    # Create a simple coroutine
    async def test_coro():
        return "test_result"

    # Enqueue the request
    await request_queue.enqueue(guild_channel, test_coro())

    # Verify typing was called
    assert typing_called, "typing() should be called for guild channels"


@pytest.mark.asyncio
async def test_request_processes_successfully_in_dm(
    request_queue: RequestQueue,
) -> None:
    """LLM request should complete successfully in DM even without typing."""
    # Create a mock DM channel
    dm_channel = AsyncMock(spec=discord.DMChannel)
    dm_channel.id = 12345

    # Create a coroutine that returns a result
    async def test_coro():
        await asyncio.sleep(0.01)  # Simulate work
        return "success"

    # Enqueue and wait for completion
    result = await request_queue.enqueue(dm_channel, test_coro())

    # Verify the request was processed
    assert result is True, "Enqueue should return True on success"


@pytest.mark.asyncio
async def test_request_processes_successfully_in_guild(
    request_queue: RequestQueue,
) -> None:
    """LLM request should complete successfully in guild with typing."""
    # Create a mock guild channel
    guild_channel = AsyncMock(spec=discord.TextChannel)
    guild_channel.id = 12345

    class AsyncTypingContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    guild_channel.typing = MagicMock(return_value=AsyncTypingContext())

    # Create a coroutine that returns a result
    async def test_coro():
        await asyncio.sleep(0.01)  # Simulate work
        return "success"

    # Enqueue and wait for completion
    result = await request_queue.enqueue(guild_channel, test_coro())

    # Verify the request was processed
    assert result is True, "Enqueue should return True on success"
