"""Tests for MessageCog on_message handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


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
    bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
    bot.history_store.get = AsyncMock(return_value=[])
    bot.history_store.append = AsyncMock()
    # Personality strings used by on_message
    bot.personality = MagicMock()
    bot.personality.empty_mention_reply = "You said nothing!"
    bot.personality.rate_limited_reply = "Too many messages!"
    bot.personality.llm_error_reply = "Something went wrong!"
    return bot


class TestMessageCogLLMPath:
    """Tests that exercise the _call_llm closure (awaited, not just enqueued)."""

    async def test_llm_call_sends_history_and_verbosity(self) -> None:
        """The enqueued coroutine fetches verbosity + history then calls llm_client.chat."""
        from common.events.messages import MessageCog

        bot = _make_bot()
        bot.verbosity_store.get_verbosity = AsyncMock(return_value=3)
        bot.history_store.get = AsyncMock(return_value=[{"role": "user", "content": "prior"}])

        # Capture the coroutine passed to enqueue so we can await it
        captured_coro = None

        async def _capture_enqueue(_channel, coro):
            nonlocal captured_coro
            captured_coro = coro

        bot.request_queue.enqueue = AsyncMock(side_effect=_capture_enqueue)

        cog = MessageCog(bot)
        await cog.on_message(_make_message(500))

        assert captured_coro is not None
        await captured_coro

        bot.verbosity_store.get_verbosity.assert_awaited_once_with(777)
        bot.history_store.get.assert_awaited_once_with(888, 777)
        bot.llm_client.chat.assert_awaited_once_with(
            "hello",
            verbosity=3,
            history=[{"role": "user", "content": "prior"}],
        )

    async def test_llm_call_appends_history_after_response(self) -> None:
        """After a successful LLM response, the exchange is appended to history."""
        from common.events.messages import MessageCog

        bot = _make_bot()
        bot.llm_client.chat = AsyncMock(return_value={"reply": "bye", "request_id": "y"})

        captured_coro = None

        async def _capture_enqueue(_channel, coro):
            nonlocal captured_coro
            captured_coro = coro

        bot.request_queue.enqueue = AsyncMock(side_effect=_capture_enqueue)

        cog = MessageCog(bot)
        await cog.on_message(_make_message(501))

        assert captured_coro is not None
        await captured_coro

        bot.history_store.append.assert_awaited_once_with(888, 777, "hello", "bye")

    async def test_history_fetch_failure_degrades_gracefully(self) -> None:
        """If history_store.get raises, chat is still called with empty history."""
        from common.events.messages import MessageCog

        bot = _make_bot()
        bot.history_store.get = AsyncMock(side_effect=ConnectionError("redis down"))

        captured_coro = None

        async def _capture_enqueue(_channel, coro):
            nonlocal captured_coro
            captured_coro = coro

        bot.request_queue.enqueue = AsyncMock(side_effect=_capture_enqueue)

        cog = MessageCog(bot)
        await cog.on_message(_make_message(502))

        assert captured_coro is not None
        await captured_coro

        bot.llm_client.chat.assert_awaited_once()
        _, kwargs = bot.llm_client.chat.call_args
        assert kwargs["history"] == []


class TestMessageCogDedup:
    async def test_first_message_is_processed(self) -> None:
        """Normal message goes through — enqueue is called once."""
        from common.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)

        await cog.on_message(_make_message(111))

        bot.request_queue.enqueue.assert_called_once()

    async def test_duplicate_message_id_is_skipped(self) -> None:
        """Second on_message call with the same message.id is a no-op."""
        from common.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)
        msg = _make_message(222)

        await cog.on_message(msg)
        await cog.on_message(msg)  # simulate gateway replay

        # enqueue should only have been called for the first delivery
        bot.request_queue.enqueue.assert_called_once()

    async def test_different_message_ids_both_processed(self) -> None:
        """Two messages with different IDs are each processed independently."""
        from common.events.messages import MessageCog

        bot = _make_bot()
        cog = MessageCog(bot)

        await cog.on_message(_make_message(333))
        await cog.on_message(_make_message(444))

        assert bot.request_queue.enqueue.call_count == 2

    async def test_dedup_cache_capacity(self) -> None:
        """maxlen=1000 eviction: after the cache fills and rolls over, evicted IDs are reprocessed."""
        from common.events.messages import MessageCog

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
