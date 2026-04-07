"""The /intensity slash command — set or view preferred brat intensity level."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.utils.age_gate import _reply, check_age_verified
from bratbot.utils.logger import get_logger

if TYPE_CHECKING:
    from bratbot.bot import BratBot

log = get_logger(__name__)


class IntensityCog(commands.Cog):
    """Slash command for managing brat intensity preference."""

    def __init__(self, bot: BratBot) -> None:
        self.bot = bot

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(
        name="intensity", description="Set or view your preferred brat intensity"
    )
    @app_commands.describe(
        intensity="Brat intensity level (1-3): 1=mild, 2=medium, 3=maximum"
    )
    async def intensity(
        self,
        interaction: discord.Interaction,
        intensity: app_commands.Range[int, 1, 3] | None = None,
    ) -> None:
        async def _run(active_interaction: discord.Interaction) -> None:
            user_id = active_interaction.user.id

            if intensity is not None:
                await self.bot.intensity_store.set_intensity(user_id, intensity)
                log.info("intensity_set", user_id=user_id, intensity=intensity)
                await _reply(
                    active_interaction,
                    f"\u2713 Your brat intensity is now **{intensity}** "
                    f"(1=mild, 2=medium, 3=maximum)",
                )
            else:
                was_explicitly_set = await self.bot.intensity_store.was_set(user_id)
                log.info(
                    "intensity_get", user_id=user_id, was_set=was_explicitly_set
                )
                if was_explicitly_set:
                    current = await self.bot.intensity_store.get_intensity(user_id)
                    await _reply(
                        active_interaction,
                        f"Your current brat intensity is **{current}** "
                        f"(1=mild, 2=medium, 3=maximum)",
                    )
                else:
                    await _reply(
                        active_interaction,
                        "You haven't set a preferred intensity yet. "
                        "Use `/intensity <1-3>` to set one, or the bot will "
                        "use the default (3=maximum).",
                    )

        if not await check_age_verified(interaction, self.bot, _run):
            return
        await _run(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IntensityCog(bot))  # type: ignore[arg-type]
