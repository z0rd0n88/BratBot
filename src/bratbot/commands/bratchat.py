"""The /bratchat slash command — ask the brat a question."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.services.llm_client import LLMError
from bratbot.utils.logger import get_logger

if TYPE_CHECKING:
    from bratbot.bot import BratBot

log = get_logger(__name__)

RATE_LIMITED_REPLY = "Slow down. I have better things to do."
LLM_ERROR_REPLY = "Something went wrong with my brain. Try again, or don't. I don't care."


class BratCog(commands.Cog):
    """Slash command for querying the brat LLM."""

    def __init__(self, bot: BratBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="bratchat", description="Ask the brat a question")
    @app_commands.describe(
        message="What do you want to say?",
        brat_level="How bratty? (1-3, default: server setting)",
    )
    async def bratchat(
        self,
        interaction: discord.Interaction,
        message: str,
        brat_level: app_commands.Range[int, 1, 3] | None = None,
    ) -> None:
        # Rate limit check
        guild_id = interaction.guild_id or 0
        if not await self.bot.rate_limiter.check_user(interaction.user.id, guild_id):
            await interaction.response.send_message(RATE_LIMITED_REPLY, ephemeral=True)
            return
        if interaction.channel and not await self.bot.rate_limiter.check_channel(
            interaction.channel.id,
        ):
            await interaction.response.send_message(RATE_LIMITED_REPLY, ephemeral=True)
            return

        # Defer — LLM may take longer than Discord's 3-second interaction timeout
        await interaction.response.defer()

        log.info(
            "bratchat_command",
            guild_id=guild_id,
            user_id=interaction.user.id,
            brat_level=brat_level,
            message_length=len(message),
        )

        async def _call_llm() -> None:
            response = await self.bot.llm_client.chat(message, brat_level=brat_level)
            await interaction.followup.send(response["reply"])

        try:
            if interaction.channel is not None:
                await self.bot.request_queue.enqueue(interaction.channel, _call_llm())
            else:
                await _call_llm()
        except (LLMError, KeyError):
            await interaction.followup.send(LLM_ERROR_REPLY)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BratCog(bot))  # type: ignore[arg-type]
