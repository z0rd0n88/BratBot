"""Entry point: python -m bratbot"""

from bratbot.config import settings
from common.utils.logger import setup_logging

setup_logging(settings.log_level)

from bratbot.bot import BratBot  # noqa: E402 — must import after logging is configured

bot = BratBot()
bot.run(settings.discord_bot_token, log_handler=None)
