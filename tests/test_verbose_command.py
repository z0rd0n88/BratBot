"""Tests for the /verbose slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestVerboseCommand:
    async def test_verbose_set_calls_store(self) -> None:
        """Setting verbosity calls set_verbosity with the correct user and level."""
        from bratbot.commands.verbose import VerboseCog

        mock_bot = AsyncMock()
        mock_bot.verbosity_store = AsyncMock()
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = VerboseCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.verbose.callback(cog, mock_interaction, verbosity=2)

        mock_bot.verbosity_store.set_verbosity.assert_called_once_with(123456, 2)
        mock_interaction.response.send_message.assert_called_once()
        assert "2" in mock_interaction.response.send_message.call_args[0][0]

    async def test_verbose_get_when_not_set(self) -> None:
        """Getting verbosity when not set shows default message."""
        from bratbot.commands.verbose import VerboseCog

        mock_bot = AsyncMock()
        mock_bot.verbosity_store = AsyncMock()
        mock_bot.verbosity_store.was_set.return_value = False
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = VerboseCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.verbose.callback(cog, mock_interaction, verbosity=None)

        mock_bot.verbosity_store.was_set.assert_called_once_with(123456)
        mock_interaction.response.send_message.assert_called_once()

    async def test_verbose_get_when_set(self) -> None:
        """Getting verbosity when set shows current level."""
        from bratbot.commands.verbose import VerboseCog

        mock_bot = AsyncMock()
        mock_bot.verbosity_store = AsyncMock()
        mock_bot.verbosity_store.was_set.return_value = True
        mock_bot.verbosity_store.get_verbosity.return_value = 3
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = VerboseCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.verbose.callback(cog, mock_interaction, verbosity=None)

        mock_bot.verbosity_store.was_set.assert_called_once_with(123456)
        call_text = mock_interaction.response.send_message.call_args[0][0]
        assert "3" in call_text

    async def test_verbose_returns_early_when_unverified(self) -> None:
        """verbose returns without accessing store when age gate returns False."""
        from bratbot.commands.verbose import VerboseCog

        mock_bot = AsyncMock()
        mock_bot.verbosity_store = AsyncMock()

        cog = VerboseCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        with patch("bratbot.commands.verbose.check_age_verified", new_callable=AsyncMock) as mock_gate:
            mock_gate.return_value = False
            await cog.verbose.callback(cog, mock_interaction, verbosity=2)

        mock_bot.verbosity_store.set_verbosity.assert_not_called()
