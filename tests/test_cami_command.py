"""Tests for the /camichat slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestCamiCommand:
    async def test_camichat_executes_when_verified(self) -> None:
        """camichat calls LLM with pronoun when user is age-verified."""
        from bratbot.commands.cami import CamiCog

        mock_bot = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
        mock_bot.pronoun_store.get_pronoun = AsyncMock(return_value="male")
        mock_bot.cami_llm_client.chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = CamiCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None
        interaction.response.is_done = MagicMock(return_value=False)

        await cog.camichat.callback(cog, interaction, message="hello")

        mock_bot.cami_llm_client.chat.assert_called_once()

    async def test_camichat_passes_female_pronoun(self) -> None:
        """camichat passes the user's female pronoun to cami_llm_client.chat()."""
        from bratbot.commands.cami import CamiCog

        mock_bot = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
        mock_bot.pronoun_store.get_pronoun = AsyncMock(return_value="female")
        mock_bot.cami_llm_client.chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = CamiCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None
        interaction.response.is_done = MagicMock(return_value=False)

        await cog.camichat.callback(cog, interaction, message="hello")

        mock_bot.cami_llm_client.chat.assert_called_once_with(
            "hello", verbosity=2, pronoun="female"
        )

    async def test_camichat_returns_early_when_unverified(self) -> None:
        """camichat returns without calling LLM when age gate returns False."""
        from bratbot.commands.cami import CamiCog

        mock_bot = AsyncMock()
        mock_bot.cami_llm_client = AsyncMock()

        cog = CamiCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456

        with patch("bratbot.commands.cami.check_age_verified", new_callable=AsyncMock) as mock_gate:
            mock_gate.return_value = False
            await cog.camichat.callback(cog, interaction, message="hello")

        mock_bot.cami_llm_client.chat.assert_not_called()
