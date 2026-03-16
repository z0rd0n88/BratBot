from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bratbot.services.llm_client import LLMError
from bratbot.utils.logger import get_logger

if TYPE_CHECKING:
    from bratbot.bot import BratBot

log = get_logger(__name__)

RATE_LIMITED_REPLY = "Slow down. I have better things to do."
EMPTY_MENTION_REPLY = "You pinged me just to say nothing? Classic."
LLM_ERROR_REPLY = "Something went wrong with my brain. Try again, or don't. I don't care."


class MessageCog(commands.Cog):
    """Handles incoming messages — routes bot mentions through the LLM pipeline."""

    def __init__(self, bot: BratBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore bots (including self) and DMs
        if message.author.bot or message.guild is None:
            return

        # Check if the bot was mentioned
        if not (self.bot.user and self.bot.user.mentioned_in(message)):
            return

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
            await message.reply(EMPTY_MENTION_REPLY)
            return

        # Rate limit checks
        if not await self.bot.rate_limiter.check_user(message.author.id, message.guild.id):
            await message.reply(RATE_LIMITED_REPLY)
            return
        if not await self.bot.rate_limiter.check_channel(message.channel.id):
            return  # Silently drop — channel is saturated

        # Build LLM coroutine and enqueue
        async def _call_llm() -> None:
            response = await self.bot.llm_client.chat(content)
            await message.reply(response["reply"])

        try:
            await self.bot.request_queue.enqueue(message.channel, _call_llm())
        except LLMError:
            await message.reply(LLM_ERROR_REPLY)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageCog(bot))  # type: ignore[arg-type]
