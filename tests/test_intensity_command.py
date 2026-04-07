"""Tests for the /intensity slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestIntensityCommand:
    """Test the /intensity command."""

    async def test_intensity_set_valid_level(self) -> None:
        """Setting intensity to valid level succeeds."""
        from bratbot.commands.intensity import IntensityCog

        mock_bot = AsyncMock()
        mock_store = AsyncMock()
        mock_bot.intensity_store = mock_store
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = IntensityCog(mock_bot)

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.intensity.callback(cog, mock_interaction, intensity=2)

        mock_store.set_intensity.assert_called_once_with(123456, 2)
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[0][0]
        assert "2" in call_args

    async def test_intensity_get_when_not_set(self) -> None:
        """Getting intensity when not set shows default message."""
        from bratbot.commands.intensity import IntensityCog

        mock_bot = AsyncMock()
        mock_store = AsyncMock()
        mock_store.was_set.return_value = False
        mock_bot.intensity_store = mock_store
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = IntensityCog(mock_bot)

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.intensity.callback(cog, mock_interaction, intensity=None)

        mock_store.was_set.assert_called_once_with(123456)
        mock_interaction.response.send_message.assert_called_once()

    async def test_intensity_get_when_set(self) -> None:
        """Getting intensity when set shows current setting."""
        from bratbot.commands.intensity import IntensityCog

        mock_bot = AsyncMock()
        mock_store = AsyncMock()
        mock_store.was_set.return_value = True
        mock_store.get_intensity.return_value = 2
        mock_bot.intensity_store = mock_store
        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        cog = IntensityCog(mock_bot)

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.intensity.callback(cog, mock_interaction, intensity=None)

        mock_store.was_set.assert_called_once_with(123456)
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[0][0]
        assert "2" in call_args

    async def test_intensity_returns_early_when_unverified(self) -> None:
        """intensity returns without accessing store when age gate returns False."""
        from bratbot.commands.intensity import IntensityCog

        mock_bot = AsyncMock()
        mock_bot.intensity_store = AsyncMock()

        cog = IntensityCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        with patch("bratbot.commands.intensity.check_age_verified", new_callable=AsyncMock) as mock_gate:
            mock_gate.return_value = False
            await cog.intensity.callback(cog, mock_interaction, intensity=2)

        mock_bot.intensity_store.set_intensity.assert_not_called()
