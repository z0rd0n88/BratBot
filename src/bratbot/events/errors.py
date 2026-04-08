"""Global error handling for commands and app command tree errors."""

from __future__ import annotations

import traceback

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.utils.logger import get_logger

log = get_logger(__name__)


class ErrorHandlerCog(commands.Cog):
    """Global error handler for prefix commands and app command tree."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Override the tree's error handler
        self.bot.tree.on_error = self.on_app_command_error

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle errors from prefix commands."""
        self._log_error(
            ctx.guild,
            ctx.channel,
            ctx.author,
            command=ctx.command.qualified_name if ctx.command else "unknown",
            error=error,
        )

        if isinstance(error, commands.CommandNotFound):
            return  # Silently ignore unknown prefix commands
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(self.bot.personality.permission_error)
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(self.bot.personality.cooldown_error)
            return

        await ctx.send(self.bot.personality.generic_error)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Handle errors from slash commands (app commands)."""
        command_name = interaction.command.name if interaction.command else "unknown"
        self._log_error(
            interaction.guild,
            interaction.channel,
            interaction.user,
            command=command_name,
            error=error,
        )

        message = self._get_error_message(error)
        await self._send_error_response(interaction, message)

    def _get_error_message(self, error: Exception) -> str:
        """Map known error types to in-character responses."""
        # Unwrap the original exception if wrapped
        original = getattr(error, "original", error)

        p = self.bot.personality

        # Discord API errors
        if isinstance(original, discord.HTTPException):
            if original.status == 429:
                retry_after = getattr(original, "retry_after", None)
                log.warning("discord_rate_limited", retry_after=retry_after)
                return p.discord_rate_limit_error
            return p.generic_error

        # Permission errors
        if isinstance(error, app_commands.MissingPermissions):
            return p.permission_error

        # Cooldown
        if isinstance(error, app_commands.CommandOnCooldown):
            return p.cooldown_error

        # Command not found
        if isinstance(error, app_commands.CommandNotFound):
            return p.not_found_error

        # LLM client errors
        from bratbot.services.llm_client import (
            LLMConnectionError,
            LLMError,
            LLMServerError,
            LLMTimeoutError,
            LLMValidationError,
            LLMWarmingError,
        )

        if isinstance(original, LLMWarmingError):
            return p.llm_warming_up_reply
        if isinstance(original, LLMConnectionError):
            return p.llm_connection_error
        if isinstance(original, LLMTimeoutError):
            return p.llm_timeout_error
        if isinstance(original, LLMServerError):
            return p.llm_server_error
        if isinstance(original, LLMValidationError):
            return p.llm_validation_error
        if isinstance(original, LLMError):
            return p.llm_generic_error

        return p.generic_error

    def _log_error(
        self,
        guild: discord.Guild | None,
        channel: discord.abc.Messageable,
        user: discord.User | discord.Member,
        *,
        command: str,
        error: Exception,
    ) -> None:
        """Log error with full structured context."""
        original = getattr(error, "original", error)
        log.error(
            "command_error",
            guild_id=guild.id if guild else None,
            channel_id=getattr(channel, "id", None),
            user_id=user.id,
            command=command,
            error_type=type(original).__name__,
            error=str(original),
            traceback=traceback.format_exception(original),
        )

    @staticmethod
    async def _send_error_response(interaction: discord.Interaction, message: str) -> None:
        """Send an error response, handling both responded and deferred states."""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            # If we can't even send the error message, just log it
            log.error("error_response_failed", message=message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErrorHandlerCog(bot))
