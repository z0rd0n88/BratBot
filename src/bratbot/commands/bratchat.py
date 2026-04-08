"""The /bratchat slash command — ask the brat a question."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.services.llm_client import LLMError, LLMWarmingError
from bratbot.utils.age_gate import _reply, check_age_verified
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
    )
    async def bratchat(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        async def _run(active_interaction: discord.Interaction) -> None:
            guild_id = active_interaction.guild_id or 0
            if not await self.bot.rate_limiter.check_user(active_interaction.user.id, guild_id):
                await _reply(active_interaction, RATE_LIMITED_REPLY, ephemeral=True)
                return
            if active_interaction.channel and not await self.bot.rate_limiter.check_channel(
                active_interaction.channel.id,
            ):
                await _reply(active_interaction, RATE_LIMITED_REPLY, ephemeral=True)
                return

            if not active_interaction.response.is_done():
                await active_interaction.response.defer()

            user_intensity = await self.bot.intensity_store.get_intensity(
                active_interaction.user.id
            )
            user_verbosity = await self.bot.verbosity_store.get_verbosity(
                active_interaction.user.id
            )

            log.info(
                "bratchat_command",
                guild_id=guild_id,
                user_id=active_interaction.user.id,
                user_intensity=user_intensity,
                user_verbosity=user_verbosity,
                message_length=len(message),
            )

            async def _call_llm() -> None:
                response = await self.bot.llm_client.chat(
                    message, brat_level=user_intensity, verbosity=user_verbosity
                )
                await active_interaction.followup.send(f"> {message}\n\n{response['reply']}")

            try:
                if active_interaction.channel is not None:
                    await self.bot.request_queue.enqueue(active_interaction.channel, _call_llm())
                else:
                    await _call_llm()
            except LLMWarmingError:
                await active_interaction.followup.send(
                    self.bot.personality.llm_warming_up_reply
                )
            except (LLMError, KeyError):
                await active_interaction.followup.send(LLM_ERROR_REPLY)

        if not await check_age_verified(interaction, self.bot, _run):
            return
        await _run(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BratCog(bot))  # type: ignore[arg-type]
