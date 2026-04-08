"""Tests for the BratBot /pronoun slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestPronounCommand:
    async def test_pronoun_set_female(self) -> None:
        """Setting pronoun to female calls set_pronoun and sends confirmation."""
        from bratbot.commands.pronoun import PronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = PronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        choice = MagicMock()
        choice.value = "female"

        await cog.pronoun.callback(cog, mock_interaction, pronoun=choice)

        mock_bot.pronoun_store.set_pronoun.assert_called_once_with(123456, "female")
        mock_interaction.response.send_message.assert_called_once()

    async def test_pronoun_get_when_not_set(self) -> None:
        """Getting pronoun when not set shows default message."""
        from bratbot.commands.pronoun import PronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()
        mock_bot.pronoun_store.was_set.return_value = False
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = PronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.pronoun.callback(cog, mock_interaction, pronoun=None)

        mock_bot.pronoun_store.was_set.assert_called_once_with(123456)
        mock_interaction.response.send_message.assert_called_once()

    async def test_pronoun_get_when_set(self) -> None:
        """Getting pronoun when set shows current preference."""
        from bratbot.commands.pronoun import PronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()
        mock_bot.pronoun_store.was_set.return_value = True
        mock_bot.pronoun_store.get_pronoun.return_value = "female"
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = PronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.pronoun.callback(cog, mock_interaction, pronoun=None)

        mock_bot.pronoun_store.was_set.assert_called_once_with(123456)
        call_text = mock_interaction.response.send_message.call_args[0][0]
        assert "female" in call_text

    async def test_pronoun_returns_early_when_unverified(self) -> None:
        """pronoun returns without accessing store when age gate returns False."""
        from bratbot.commands.pronoun import PronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()

        cog = PronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        with patch(
            "bratbot.commands.pronoun.check_age_verified", new_callable=AsyncMock
        ) as mock_gate:
            mock_gate.return_value = False
            choice = MagicMock()
            choice.value = "female"
            await cog.pronoun.callback(cog, mock_interaction, pronoun=choice)

        mock_bot.pronoun_store.set_pronoun.assert_not_called()
