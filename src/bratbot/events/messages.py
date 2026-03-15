import discord
from discord.ext import commands

from bratbot.utils.logger import get_logger

log = get_logger(__name__)


class MessageCog(commands.Cog):
    """Handles incoming messages — detects bot mentions for conversation routing."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore messages from bots (including self)
        if message.author.bot:
            return

        # Check if the bot was mentioned
        if self.bot.user and self.bot.user.mentioned_in(message):
            log.debug(
                "bot_mentioned",
                guild_id=message.guild.id if message.guild else None,
                channel_id=message.channel.id,
                user_id=message.author.id,
            )
            # Phase 4 will wire this to the LLM conversation pipeline.
            # For now, just acknowledge the mention.


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageCog(bot))
