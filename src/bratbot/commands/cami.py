"""The /camichat slash command — ask Cami a question."""

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

WARMING_UP_REPLY = "I-I'm so sorry... the brain is still waking up... please be patient with me..."


def _cami_replies(pronoun: str) -> tuple[str, str]:
    """Return (rate_limited_reply, llm_error_reply) for the user's pronoun preference."""
    if pronoun == "female":
        return (
            "P-please Mommy... I need a moment to catch my breath... I'm sorry...",
            "I-I'm so sorry Mommy, my brain broke... please don't be mad at me...",
        )
    if pronoun == "other":
        return (
            "P-please... I need a moment to catch my breath... I'm sorry...",
            "I-I'm so sorry, my brain broke... please don't be mad at me...",
        )
    # default: male
    return (
        "P-please Daddy... I need a moment to catch my breath... I'm sorry...",
        "I-I'm so sorry Daddy, my brain broke... please don't be mad at me...",
    )


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
            user_id = active_interaction.user.id
            guild_id = active_interaction.guild_id or 0

            user_pronoun = await self.bot.pronoun_store.get_pronoun(user_id)
            rate_limited_reply, llm_error_reply = _cami_replies(user_pronoun)

            if not await self.bot.rate_limiter.check_user(user_id, guild_id):
                await _reply(active_interaction, rate_limited_reply, ephemeral=True)
                return
            if active_interaction.channel and not await self.bot.rate_limiter.check_channel(
                active_interaction.channel.id,
            ):
                await _reply(active_interaction, rate_limited_reply, ephemeral=True)
                return

            if not active_interaction.response.is_done():
                await active_interaction.response.defer()

            user_verbosity = await self.bot.verbosity_store.get_verbosity(user_id)

            log.info(
                "camichat_command",
                guild_id=guild_id,
                user_id=user_id,
                user_verbosity=user_verbosity,
                user_pronoun=user_pronoun,
                message_length=len(message),
            )

            async def _call_llm() -> None:
                response = await self.bot.cami_llm_client.chat(
                    message, verbosity=user_verbosity, pronoun=user_pronoun
                )
                await active_interaction.followup.send(f"> {message}\n\n{response['reply']}")

            try:
                if active_interaction.channel is not None:
                    await self.bot.request_queue.enqueue(active_interaction.channel, _call_llm())
                else:
                    await _call_llm()
            except LLMWarmingError:
                await active_interaction.followup.send(WARMING_UP_REPLY)
            except (LLMError, KeyError):
                await active_interaction.followup.send(llm_error_reply)

        if not await check_age_verified(interaction, self.bot, _run):
            return
        await _run(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CamiCog(bot))  # type: ignore[arg-type]
