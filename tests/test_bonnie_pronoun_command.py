"""Tests for the BonnieBot /pronoun slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


class TestBonniePronounCommand:
    async def test_pronoun_set_female(self) -> None:
        """Setting pronoun to female calls set_pronoun and sends confirmation."""
        from bonniebot.commands.pronoun import BonniePronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()

        cog = BonniePronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        choice = MagicMock()
        choice.value = "female"

        await cog.pronoun.callback(cog, mock_interaction, pronoun=choice)

        mock_bot.pronoun_store.set_pronoun.assert_called_once_with(123456, "female")
        mock_interaction.response.send_message.assert_called_once()

    async def test_pronoun_get_when_not_set(self) -> None:
        """Getting pronoun when not set shows default message."""
        from bonniebot.commands.pronoun import BonniePronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()
        mock_bot.pronoun_store.was_set.return_value = False

        cog = BonniePronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        await cog.pronoun.callback(cog, mock_interaction, pronoun=None)

        mock_bot.pronoun_store.was_set.assert_called_once_with(123456)
        mock_interaction.response.send_message.assert_called_once()

    async def test_pronoun_get_when_set(self) -> None:
        """Getting pronoun when set shows current preference."""
        from bonniebot.commands.pronoun import BonniePronounCog

        mock_bot = AsyncMock()
        mock_bot.pronoun_store = AsyncMock()
        mock_bot.pronoun_store.was_set.return_value = True
        mock_bot.pronoun_store.get_pronoun.return_value = "other"

        cog = BonniePronounCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        await cog.pronoun.callback(cog, mock_interaction, pronoun=None)

        call_text = mock_interaction.response.send_message.call_args[0][0]
        assert "other" in call_text
