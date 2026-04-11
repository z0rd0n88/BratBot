from __future__ import annotations

import asyncio
import pkgutil
import sys
import traceback

import discord
from discord.ext import commands

from bratbot.config import settings
from bratbot.personality import BRAT_PERSONALITY, Personality
from bratbot.services.age_verification_store import AgeVerificationStore
from common.services.conversation_history import ConversationHistoryStore
from common.services.llm_client import LLMClient
from common.services.pronoun_store import PronounStore
from common.services.rate_limiter import RateLimiter
from common.services.request_queue import RequestQueue
from common.services.verbosity_store import VerbosityStore
from common.utils.logger import get_logger
from common.utils.redis import close_redis, get_redis

log = get_logger(__name__)

# Packages to auto-discover cog modules from
_COG_PACKAGES = ("bratbot.commands", "common.events")


class BratBot(commands.Bot):
    personality: Personality
    llm_client: LLMClient
    cami_llm_client: LLMClient
    request_queue: RequestQueue
    rate_limiter: RateLimiter
    verbosity_store: VerbosityStore
    age_verification_store: AgeVerificationStore
    pronoun_store: PronounStore
    history_store: ConversationHistoryStore
    cami_history_store: ConversationHistoryStore

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        intents.guild_reactions = True

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        # Attach personality
        self.personality = BRAT_PERSONALITY

        # Initialize Redis
        redis = await get_redis(settings.redis_url)
        log.info("redis_initialized")

        # Initialize LLM client
        self.llm_client = LLMClient(
            base_url=settings.llm_api_url,
            chat_endpoint=self.personality.chat_endpoint,
            timeout=settings.llm_timeout_seconds,
        )
        self.cami_llm_client = LLMClient(
            base_url=settings.llm_api_url,
            chat_endpoint="/camichat",
            timeout=settings.llm_timeout_seconds,
        )
        healthy = await self.llm_client.health_check()
        if healthy:
            log.info("llm_server_healthy", url=settings.llm_api_url)
        else:
            log.warning("llm_server_unhealthy", url=settings.llm_api_url)

        # Initialize services
        self.request_queue = RequestQueue()
        self.rate_limiter = RateLimiter(redis)
        self.verbosity_store = VerbosityStore(redis)
        self.age_verification_store = AgeVerificationStore(redis)
        self.pronoun_store = PronounStore(redis)
        self.history_store = ConversationHistoryStore(redis, "bratbot", settings.history_size)
        self.cami_history_store = ConversationHistoryStore(redis, "cami", settings.history_size)

        # Auto-discover and load all extensions
        await self._load_extensions()

        # Sync slash commands — guild-specific for dev, global for production
        if settings.guild_id:
            guild = discord.Object(id=settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("commands_synced", mode="guild", guild_id=settings.guild_id)
        else:
            await self.tree.sync()
            log.info("commands_synced", mode="global")

        # Register global exception handlers
        self._register_exception_handlers()

    async def _load_extensions(self) -> None:
        """Auto-discover and load all cog modules from commands/ and events/."""
        failed: list[str] = []
        for package_name in _COG_PACKAGES:
            pkg = __import__(package_name, fromlist=[""])
            for _importer, modname, _ispkg in pkgutil.iter_modules(pkg.__path__):
                ext = f"{package_name}.{modname}"
                try:
                    await self.load_extension(ext)
                    log.info("extension_loaded", extension=ext)
                except Exception as e:
                    log.error(
                        "extension_load_failed",
                        extension=ext,
                        error=str(e),
                        traceback=traceback.format_exc(),
                    )
                    failed.append(ext)
        if failed:
            raise RuntimeError(f"Failed to load extensions: {failed}")

    def _register_exception_handlers(self) -> None:
        """Register sys.excepthook and asyncio exception handler for unhandled errors."""
        original_excepthook = sys.excepthook

        def _excepthook(exc_type: type, exc_value: BaseException, exc_tb: object) -> None:
            log.error(
                "unhandled_exception",
                exc_type=exc_type.__name__,
                error=str(exc_value),
                traceback=traceback.format_exception(exc_type, exc_value, exc_tb),
            )
            original_excepthook(exc_type, exc_value, exc_tb)

        sys.excepthook = _excepthook

        loop = asyncio.get_running_loop()

        def _async_exception_handler(_loop: asyncio.AbstractEventLoop, context: dict) -> None:
            exception = context.get("exception")
            message = context.get("message", "Unhandled async exception")
            log.error(
                "unhandled_async_exception",
                message=message,
                error=str(exception) if exception else None,
                traceback=traceback.format_exception(exception) if exception else None,
            )

        loop.set_exception_handler(_async_exception_handler)

    async def close(self) -> None:
        if hasattr(self, "llm_client"):
            await self.llm_client.close()
        if hasattr(self, "cami_llm_client"):
            await self.cami_llm_client.close()
        await close_redis()
        log.info("connections_closed")
        await super().close()
