"""Tests for the /intensity slash command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from discord import Interaction

    from bratbot.bot import BratBot


class TestIntensityCommand:
    """Test the /intensity command."""

    async def test_intensity_set_valid_level(self) -> None:
        """Setting intensity to valid level succeeds."""
        from bratbot.commands.intensity import IntensityCog

        # Create mocks
        mock_bot = AsyncMock(spec=["intensity_store"])
        mock_store = AsyncMock()
        mock_bot.intensity_store = mock_store

        cog = IntensityCog(mock_bot)

        # Create mock interaction
        mock_interaction = AsyncMock(spec=["response", "user"])
        mock_interaction.user.id = 123456
        mock_interaction.response.send_message = AsyncMock()

        # Call command with intensity=2 (bypass decorator by calling callback)
        await cog.intensity.callback(cog, mock_interaction, intensity=2)

        # Verify set_intensity was called
        mock_store.set_intensity.assert_called_once_with(123456, 2)

        # Verify user got a confirmation message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[0][0]
        assert "2" in call_args

    async def test_intensity_get_when_not_set(self) -> None:
        """Getting intensity when not set shows default message."""
        from bratbot.commands.intensity import IntensityCog

        mock_bot = AsyncMock(spec=["intensity_store"])
        mock_store = AsyncMock()
        mock_store.was_set.return_value = False
        mock_bot.intensity_store = mock_store

        cog = IntensityCog(mock_bot)

        mock_interaction = AsyncMock(spec=["response", "user"])
        mock_interaction.user.id = 123456
        mock_interaction.response.send_message = AsyncMock()

        # Call without intensity argument
        await cog.intensity.callback(cog, mock_interaction, intensity=None)

        # Verify was_set was called
        mock_store.was_set.assert_called_once_with(123456)

        # Verify user got a message about no explicit setting
        mock_interaction.response.send_message.assert_called_once()

    async def test_intensity_get_when_set(self) -> None:
        """Getting intensity when set shows current setting."""
        from bratbot.commands.intensity import IntensityCog

        mock_bot = AsyncMock(spec=["intensity_store"])
        mock_store = AsyncMock()
        mock_store.was_set.return_value = True
        mock_store.get_intensity.return_value = 2
        mock_bot.intensity_store = mock_store

        cog = IntensityCog(mock_bot)

        mock_interaction = AsyncMock(spec=["response", "user"])
        mock_interaction.user.id = 123456
        mock_interaction.response.send_message = AsyncMock()

        # Call without intensity argument
        await cog.intensity.callback(cog, mock_interaction, intensity=None)

        # Verify was_set was called
        mock_store.was_set.assert_called_once_with(123456)

        # Verify user got current setting in message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[0][0]
        assert "2" in call_args
