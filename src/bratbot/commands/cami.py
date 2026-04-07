"""The /camichat slash command — ask Cami a question."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.services.llm_client import LLMError
from bratbot.utils.age_gate import _reply, check_age_verified
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
        async def _run(active_interaction: discord.Interaction) -> None:
            guild_id = active_interaction.guild_id or 0
            if not await self.bot.rate_limiter.check_user(
                active_interaction.user.id, guild_id
            ):
                await _reply(active_interaction, RATE_LIMITED_REPLY, ephemeral=True)
                return
            if (
                active_interaction.channel
                and not await self.bot.rate_limiter.check_channel(
                    active_interaction.channel.id,
                )
            ):
                await _reply(active_interaction, RATE_LIMITED_REPLY, ephemeral=True)
                return

            if not active_interaction.response.is_done():
                await active_interaction.response.defer()

            user_verbosity = await self.bot.verbosity_store.get_verbosity(
                active_interaction.user.id
            )

            log.info(
                "camichat_command",
                guild_id=guild_id,
                user_id=active_interaction.user.id,
                user_verbosity=user_verbosity,
                message_length=len(message),
            )

            async def _call_llm() -> None:
                response = await self.bot.llm_client.cami_chat(
                    message, verbosity=user_verbosity
                )
                await active_interaction.followup.send(response["reply"])

            try:
                if active_interaction.channel is not None:
                    await self.bot.request_queue.enqueue(
                        active_interaction.channel, _call_llm()
                    )
                else:
                    await _call_llm()
            except (LLMError, KeyError):
                await active_interaction.followup.send(LLM_ERROR_REPLY)

        if not await check_age_verified(interaction, self.bot, _run):
            return
        await _run(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CamiCog(bot))  # type: ignore[arg-type]
