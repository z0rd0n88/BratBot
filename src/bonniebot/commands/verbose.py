"""The /verbose slash command — set or view preferred response length."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from common.utils.logger import get_logger

if TYPE_CHECKING:
    from bonniebot.bot import BonnieBot

log = get_logger(__name__)


class VerboseCog(commands.Cog):
    """Slash command for managing verbosity preference."""

    def __init__(self, bot: BonnieBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="verbose", description="Set or view your preferred response length")
    @app_commands.describe(verbosity="Response length (1-3): 1=short, 2=medium, 3=long")
    async def verbose(
        self,
        interaction: discord.Interaction,
        verbosity: app_commands.Range[int, 1, 3] | None = None,
    ) -> None:
        user_id = interaction.user.id

        if verbosity is not None:
            await self.bot.verbosity_store.set_verbosity(user_id, verbosity)
            log.info("verbosity_set", user_id=user_id, verbosity=verbosity)
            await interaction.response.send_message(
                f"Got it! Your response length is now **{verbosity}** (1=short, 2=medium, 3=long)"
            )
        else:
            was_explicitly_set = await self.bot.verbosity_store.was_set(user_id)
            log.info("verbosity_get", user_id=user_id, was_set=was_explicitly_set)
            if was_explicitly_set:
                current = await self.bot.verbosity_store.get_verbosity(user_id)
                await interaction.response.send_message(
                    f"Your current response length is **{current}** (1=short, 2=medium, 3=long)"
                )
            else:
                await interaction.response.send_message(
                    "You haven't set a response length yet. "
                    "Use `/verbose <1-3>` to set one, or the bot will use the default (2=medium)."
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerboseCog(bot))  # type: ignore[arg-type]
