import discord
from discord.ext import commands

from common.utils.logger import get_logger

log = get_logger(__name__)


class GuildCog(commands.Cog):
    """Handles guild join and remove events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info(
            "guild_joined",
            guild_id=guild.id,
            guild_name=guild.name,
            member_count=guild.member_count,
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        log.info(
            "guild_removed",
            guild_id=guild.id,
            guild_name=guild.name,
            member_count=guild.member_count,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildCog(bot))
