"""Entry point: python -m bonniebot"""

from bonniebot.config import settings
from bratbot.utils.logger import setup_logging

setup_logging(settings.log_level)

from bonniebot.bot import BonnieBot  # noqa: E402 — must import after logging is configured

bot = BonnieBot()
bot.run(settings.discord_bot_token, log_handler=None)
