"""Tests for the /bonniebot slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


class TestBonniebotCommand:
    async def test_bonniebot_passes_male_pronoun(self) -> None:
        """male pronoun -> llm_client.chat called with pronoun='male'."""
        from bonniebot.commands.bonniebot import BonnieCog

        mock_bot = AsyncMock()
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.intensity_store.get_intensity = AsyncMock(return_value=3)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
        mock_bot.pronoun_store.get_pronoun = AsyncMock(return_value="male")
        mock_bot.llm_client.chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = BonnieCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None
        interaction.response.is_done = MagicMock(return_value=False)

        await cog.bonniebot.callback(cog, interaction, message="hello")

        mock_bot.llm_client.chat.assert_called_once_with(
            "hello", brat_level=3, verbosity=2, pronoun="male"
        )

    async def test_bonniebot_passes_female_pronoun(self) -> None:
        """female pronoun -> llm_client.chat called with pronoun='female'."""
        from bonniebot.commands.bonniebot import BonnieCog

        mock_bot = AsyncMock()
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.intensity_store.get_intensity = AsyncMock(return_value=3)
        mock_bot.verbosity_store.get_verbosity = AsyncMock(return_value=2)
        mock_bot.pronoun_store.get_pronoun = AsyncMock(return_value="female")
        mock_bot.llm_client.chat = AsyncMock(return_value={"request_id": "x", "reply": "hi"})
        mock_bot.request_queue = AsyncMock()

        cog = BonnieCog(mock_bot)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.guild_id = None
        interaction.channel = None
        interaction.response.is_done = MagicMock(return_value=False)

        await cog.bonniebot.callback(cog, interaction, message="hello")

        mock_bot.llm_client.chat.assert_called_once_with(
            "hello", brat_level=3, verbosity=2, pronoun="female"
        )
