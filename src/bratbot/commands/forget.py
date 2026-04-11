"""The /forget and /forgetall commands — clear conversation history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

from common.utils.logger import get_logger

if TYPE_CHECKING:
    from bratbot.bot import BratBot

log = get_logger(__name__)


class ForgetCog(commands.Cog):
    """Slash commands for clearing conversation history."""

    def __init__(self, bot: BratBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="forget", description="Clear conversation history for a persona")
    @app_commands.describe(persona="Which persona's history to clear")
    async def forget(
        self,
        interaction: discord.Interaction,
        persona: Literal["bratbot", "cami"],
    ) -> None:
        channel_id = interaction.channel.id if interaction.channel else 0
        user_id = interaction.user.id
        guild_id = interaction.guild_id or 0

        if persona == "cami":
            await self.bot.cami_history_store.clear(channel_id, user_id)
            reply = "I-I've forgotten everything, Daddy... our whole conversation is gone..."
        else:
            await self.bot.history_store.clear(channel_id, user_id)
            reply = "Fine. It's gone. Don't expect me to care about whatever you said before."

        log.info("history_cleared", guild_id=guild_id, user_id=user_id, persona=persona)
        await interaction.response.send_message(reply, ephemeral=True)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="forgetall", description="Clear conversation history for all personas")
    async def forgetall(self, interaction: discord.Interaction) -> None:
        channel_id = interaction.channel.id if interaction.channel else 0
        user_id = interaction.user.id
        guild_id = interaction.guild_id or 0

        await self.bot.history_store.clear_all(channel_id, user_id)

        log.info("history_cleared_all", guild_id=guild_id, user_id=user_id)
        await interaction.response.send_message(
            "All of it. Gone. Every last word. You're welcome.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ForgetCog(bot))  # type: ignore[arg-type]
