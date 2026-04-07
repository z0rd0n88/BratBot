"""The /bonniebot slash command — talk to Bonnie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.services.llm_client import LLMError
from bratbot.utils.logger import get_logger

if TYPE_CHECKING:
    from bonniebot.bot import BonnieBot

log = get_logger(__name__)


class BonnieCog(commands.Cog):
    """Slash command for querying the Bonnie LLM personality."""

    def __init__(self, bot: BonnieBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="bonniebot", description="Talk to Bonnie")
    @app_commands.describe(
        message="What do you want to say?",
    )
    async def bonniebot(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        # Rate limit check
        guild_id = interaction.guild_id or 0
        if not await self.bot.rate_limiter.check_user(interaction.user.id, guild_id):
            await interaction.response.send_message(
                self.bot.personality.rate_limited_reply, ephemeral=True
            )
            return
        if interaction.channel and not await self.bot.rate_limiter.check_channel(
            interaction.channel.id,
        ):
            await interaction.response.send_message(
                self.bot.personality.rate_limited_reply, ephemeral=True
            )
            return

        # Defer — LLM may take longer than Discord's 3-second interaction timeout
        await interaction.response.defer()

        # Get user's preferred intensity and verbosity
        user_intensity = await self.bot.intensity_store.get_intensity(interaction.user.id)
        user_verbosity = await self.bot.verbosity_store.get_verbosity(interaction.user.id)

        log.info(
            "bonniebot_command",
            guild_id=guild_id,
            user_id=interaction.user.id,
            user_intensity=user_intensity,
            user_verbosity=user_verbosity,
            message_length=len(message),
        )

        async def _call_llm() -> None:
            response = await self.bot.llm_client.chat(
                message, brat_level=user_intensity, verbosity=user_verbosity
            )
            await interaction.followup.send(response["reply"])

        try:
            if interaction.channel is not None:
                await self.bot.request_queue.enqueue(interaction.channel, _call_llm())
            else:
                await _call_llm()
        except (LLMError, KeyError):
            await interaction.followup.send(self.bot.personality.llm_error_reply)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BonnieCog(bot))  # type: ignore[arg-type]
