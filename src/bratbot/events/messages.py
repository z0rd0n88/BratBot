from __future__ import annotations

import re
from collections import deque
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bratbot.services.llm_client import LLMError, LLMWarmingError
from common.utils.logger import get_logger

if TYPE_CHECKING:
    from bratbot.bot import BratBot

log = get_logger(__name__)


class MessageCog(commands.Cog):
    """Handles incoming messages — routes bot mentions through the LLM pipeline."""

    def __init__(self, bot: BratBot) -> None:
        self.bot = bot
        # Bounded dedup cache — guards against Discord gateway event replay on reconnect,
        # which re-delivers MESSAGE_CREATE events and would otherwise trigger a second LLM call.
        self._processed_ids: deque[int] = deque(maxlen=1000)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore bots (including self) and DMs
        if message.author.bot or message.guild is None:
            return

        # Check if the bot was mentioned
        if not (self.bot.user and self.bot.user.mentioned_in(message)):
            return

        # Deduplicate: skip messages we've already processed (e.g. replayed after reconnect)
        if message.id in self._processed_ids:
            log.debug("duplicate_message_skipped", message_id=message.id)
            return
        self._processed_ids.append(message.id)

        # Strip the bot mention to get the actual message text
        content = re.sub(rf"<@!?{self.bot.user.id}>", "", message.content).strip()

        log.debug(
            "bot_mentioned",
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            user_id=message.author.id,
            content_length=len(content),
        )

        if not content:
            await message.reply(self.bot.personality.empty_mention_reply)
            return

        # Rate limit checks
        if not await self.bot.rate_limiter.check_user(message.author.id, message.guild.id):
            await message.reply(self.bot.personality.rate_limited_reply)
            return
        if not await self.bot.rate_limiter.check_channel(message.channel.id):
            return  # Silently drop — channel is saturated

        # Build LLM coroutine and enqueue
        async def _call_llm() -> None:
            response = await self.bot.llm_client.chat(content)
            await message.reply(f"> {content}\n\n{response['reply']}")

        try:
            await self.bot.request_queue.enqueue(message.channel, _call_llm())
        except LLMWarmingError:
            await message.reply(self.bot.personality.llm_warming_up_reply)
        except (LLMError, KeyError):
            await message.reply(self.bot.personality.llm_error_reply)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageCog(bot))  # type: ignore[arg-type]
