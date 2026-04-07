"""Tests that bratchat and camichat pass verbosity to the LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


class TestBratchatPassesVerbosity:
    async def test_bratchat_fetches_user_verbosity(self) -> None:
        """bratchat fetches user's verbosity before calling LLM."""
        from bratbot.commands.bratchat import BratCog

        mock_bot = AsyncMock()
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.intensity_store.get_intensity = AsyncMock(return_value=3)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
        mock_bot.llm_client.chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = BratCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None

        await cog.bratchat.callback(cog, interaction, message="hello")

        mock_bot.verbosity_store.get_verbosity.assert_called_once_with(123456)

    async def test_bratchat_passes_verbosity_to_llm(self) -> None:
        """bratchat includes verbosity in the LLM call."""
        from bratbot.commands.bratchat import BratCog

        mock_bot = AsyncMock()
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.intensity_store.get_intensity = AsyncMock(return_value=3)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=1)
        mock_bot.llm_client.chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = BratCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None

        await cog.bratchat.callback(cog, interaction, message="hello")

        mock_bot.llm_client.chat.assert_called_once()
        assert mock_bot.llm_client.chat.call_args[1]["verbosity"] == 1


class TestCamichatPassesVerbosity:
    async def test_camichat_fetches_user_verbosity(self) -> None:
        """camichat fetches user's verbosity before calling LLM."""
        from bratbot.commands.cami import CamiCog

        mock_bot = AsyncMock()
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
        mock_bot.llm_client.cami_chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = CamiCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None

        await cog.camichat.callback(cog, interaction, message="hello")

        mock_bot.verbosity_store.get_verbosity.assert_called_once_with(123456)

    async def test_camichat_passes_verbosity_to_llm(self) -> None:
        """camichat includes verbosity in the LLM call."""
        from bratbot.commands.cami import CamiCog

        mock_bot = AsyncMock()
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=3)
        mock_bot.llm_client.cami_chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = CamiCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None

        await cog.camichat.callback(cog, interaction, message="hello")

        mock_bot.llm_client.cami_chat.assert_called_once()
        assert mock_bot.llm_client.cami_chat.call_args[1]["verbosity"] == 3
