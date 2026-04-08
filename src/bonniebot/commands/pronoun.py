"""The /pronoun slash command — set or view pronoun preference."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.utils.logger import get_logger

if TYPE_CHECKING:
    from bonniebot.bot import BonnieBot

log = get_logger(__name__)

_PRONOUN_CHOICES = [
    app_commands.Choice(name="male (he/him)", value="male"),
    app_commands.Choice(name="female (she/her)", value="female"),
    app_commands.Choice(name="other (they/them)", value="other"),
]


class BonniePronounCog(commands.Cog):
    """Slash command for managing pronoun preference."""

    def __init__(self, bot: BonnieBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="pronoun", description="Set or view your pronoun preference")
    @app_commands.describe(pronoun="Your pronoun preference (affects how I address you)")
    @app_commands.choices(pronoun=_PRONOUN_CHOICES)
    async def pronoun(
        self,
        interaction: discord.Interaction,
        pronoun: app_commands.Choice[str] | None = None,
    ) -> None:
        user_id = interaction.user.id

        if pronoun is not None:
            await self.bot.pronoun_store.set_pronoun(user_id, pronoun.value)
            log.info("pronoun_set", user_id=user_id, pronoun=pronoun.value)
            await interaction.response.send_message(
                f"Got it! I'll address you as {pronoun.value}, sweetheart. \N{WINKING FACE}"
            )
        else:
            was_explicitly_set = await self.bot.pronoun_store.was_set(user_id)
            log.info("pronoun_get", user_id=user_id, was_set=was_explicitly_set)
            if was_explicitly_set:
                current = await self.bot.pronoun_store.get_pronoun(user_id)
                await interaction.response.send_message(
                    f"Your current pronoun preference is **{current}**, honey bun."
                )
            else:
                await interaction.response.send_message(
                    "You haven't set a pronoun preference yet, sweetheart. "
                    "Use `/pronoun` to set one \N{EM DASH} I'll default to male address for now."
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BonniePronounCog(bot))  # type: ignore[arg-type]
