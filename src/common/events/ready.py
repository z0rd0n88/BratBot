from discord.ext import commands

from common.utils.logger import get_logger

log = get_logger(__name__)


class ReadyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info(
            "bot_ready",
            user=str(self.bot.user),
            guild_count=len(self.bot.guilds),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReadyCog(bot))
