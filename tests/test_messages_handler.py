"""Tests for MessageCog on_message handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_message(message_id: int = 111222333) -> MagicMock:
    """Build a minimal mock Discord message that passes all on_message guards."""
    msg = MagicMock()
    msg.id = message_id
    msg.author.bot = False
    msg.guild = MagicMock()  # non-None → not a DM
    msg.guild.id = 999
    msg.channel = AsyncMock()
    msg.channel.id = 888
    msg.author.id = 777
    msg.content = "<@123456> hello"
    msg.reply = AsyncMock()
    return msg


def _make_bot() -> AsyncMock:
    """Build a minimal mock BratBot with the attributes MessageCog reads."""
    bot = AsyncMock()
    bot.user = MagicMock()
    bot.user.id = 123456
    bot.user.mentioned_in = MagicMock(return_value=True)
    bot.rate_limiter.check_user = AsyncMock(return_value=True)
    bot.rate_limiter.check_channel = AsyncMock(return_value=True)
    bot.request_queue.enqueue = AsyncMock(return_value=True)
    bot.llm_client.chat = AsyncMock(return_value={"reply": "hi", "request_id": "x"})
    # Personality strings used by on_message
    bot.personality = MagicMock()
    bot.personality.empty_mention_reply = "You said nothing!"
    bot.personality.rate_limited_reply = "Too many messages!"
    bot.personality.llm_error_reply = "Something went wrong!"
    return bot


class TestMessageCogDedup:
    async def test_first_message_is_processed(self) -> None:
        """Normal message goes through — enqueue is called once."""
        from bratbot.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)

        await cog.on_message(_make_message(111))

        bot.request_queue.enqueue.assert_called_once()

    async def test_duplicate_message_id_is_skipped(self) -> None:
        """Second on_message call with the same message.id is a no-op."""
        from bratbot.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)
        msg = _make_message(222)

        await cog.on_message(msg)
        await cog.on_message(msg)  # simulate gateway replay

        # enqueue should only have been called for the first delivery
        bot.request_queue.enqueue.assert_called_once()

    async def test_different_message_ids_both_processed(self) -> None:
        """Two messages with different IDs are each processed independently."""
        from bratbot.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)

        await cog.on_message(_make_message(333))
        await cog.on_message(_make_message(444))

        assert bot.request_queue.enqueue.call_count == 2

    async def test_dedup_cache_capacity(self) -> None:
        """maxlen=1000 eviction: after the cache fills and rolls over, evicted IDs are reprocessed."""
        from bratbot.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)

        # Fill cache to capacity with IDs 0–999
        for i in range(1000):
            await cog.on_message(_make_message(i))
        assert bot.request_queue.enqueue.call_count == 1000

        # ID 0 is still in the deque — replaying it must be silently skipped
        await cog.on_message(_make_message(0))
        assert bot.request_queue.enqueue.call_count == 1000

        # Adding ID 1000 (the 1001st unique item) evicts ID 0 from the front
        await cog.on_message(_make_message(1000))
        assert bot.request_queue.enqueue.call_count == 1001

        # Now ID 0 has been evicted — it is treated as a fresh message
        await cog.on_message(_make_message(0))
        assert bot.request_queue.enqueue.call_count == 1002
