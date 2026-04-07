"""The /camichat slash command — ask Cami a question."""

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

RATE_LIMITED_REPLY = "P-please Daddy... I need a moment to catch my breath... I'm sorry..."
LLM_ERROR_REPLY = "I-I'm so sorry Daddy, my brain broke... please don't be mad at me..."


class CamiCog(commands.Cog):
    """Slash command for querying the Cami LLM personality."""

    def __init__(self, bot: BratBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="camichat", description="Ask Cami a question")
    @app_commands.describe(message="What do you want to say?")
    async def camichat(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        guild_id = interaction.guild_id or 0
        if not await self.bot.rate_limiter.check_user(interaction.user.id, guild_id):
            await interaction.response.send_message(RATE_LIMITED_REPLY, ephemeral=True)
            return
        if interaction.channel and not await self.bot.rate_limiter.check_channel(
            interaction.channel.id,
        ):
            await interaction.response.send_message(RATE_LIMITED_REPLY, ephemeral=True)
            return

        await interaction.response.defer()

        user_verbosity = await self.bot.verbosity_store.get_verbosity(interaction.user.id)

        log.info(
            "camichat_command",
            guild_id=guild_id,
            user_id=interaction.user.id,
            user_verbosity=user_verbosity,
            message_length=len(message),
        )

        async def _call_llm() -> None:
            response = await self.bot.llm_client.cami_chat(message, verbosity=user_verbosity)
            await interaction.followup.send(response["reply"])

        try:
            if interaction.channel is not None:
                await self.bot.request_queue.enqueue(interaction.channel, _call_llm())
            else:
                await _call_llm()
        except (LLMError, KeyError):
            await interaction.followup.send(LLM_ERROR_REPLY)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CamiCog(bot))  # type: ignore[arg-type]
