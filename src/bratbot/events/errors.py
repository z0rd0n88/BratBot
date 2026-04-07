"""Global error handling for commands and app command tree errors."""

from __future__ import annotations

import traceback

import discord
from discord import app_commands
from discord.ext import commands

from bratbot.utils.logger import get_logger

log = get_logger(__name__)

# In-character error responses
GENERIC_ERROR = "Something broke. It's probably your fault, but I'll look into it."
PERMISSION_ERROR = "You don't have the permission to do that. Sad for you."
COOLDOWN_ERROR = "Slow down. I'm not a machine. Well, I am, but still."
NOT_FOUND_ERROR = "That command doesn't exist. Maybe try one that does?"


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
            await ctx.send(PERMISSION_ERROR)
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(COOLDOWN_ERROR)
            return

        await ctx.send(GENERIC_ERROR)

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

        # Discord API errors
        if isinstance(original, discord.HTTPException):
            if original.status == 429:
                retry_after = getattr(original, "retry_after", None)
                log.warning("discord_rate_limited", retry_after=retry_after)
                return "Discord told me to slow down. Try again in a sec."
            return GENERIC_ERROR

        # Permission errors
        if isinstance(error, app_commands.MissingPermissions):
            return PERMISSION_ERROR

        # Cooldown
        if isinstance(error, app_commands.CommandOnCooldown):
            return COOLDOWN_ERROR

        # Command not found
        if isinstance(error, app_commands.CommandNotFound):
            return NOT_FOUND_ERROR

        # LLM client errors
        from bratbot.services.llm_client import (
            LLMConnectionError,
            LLMError,
            LLMServerError,
            LLMTimeoutError,
            LLMValidationError,
        )

        if isinstance(original, LLMConnectionError):
            return "My brain is offline. Someone probably tripped over the server cable."
        if isinstance(original, LLMTimeoutError):
            return "I lost my train of thought. Try again, I guess."
        if isinstance(original, LLMServerError):
            return "My brain had a hiccup. Try again."
        if isinstance(original, LLMValidationError):
            return "That doesn't make sense. Even for you."
        if isinstance(original, LLMError):
            return "Something went wrong with my thinking process. Weird."

        # Database errors
        if type(original).__name__ == "OperationalError":
            log.error("database_error", error=str(original))
            return "I can't remember anything right now. Database issues."

        return GENERIC_ERROR

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
