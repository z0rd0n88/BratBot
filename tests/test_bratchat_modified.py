"""Tests for modified /bratchat command — no brat_level parameter."""

from __future__ import annotations

from inspect import signature
from unittest.mock import AsyncMock, MagicMock, patch


class TestBratChatModified:
    """Test the modified /bratchat command without brat_level parameter."""

    async def test_bratchat_no_brat_level_parameter(self) -> None:
        """bratchat command signature has no brat_level parameter."""
        from bratbot.commands.bratchat import BratCog

        # Check the command's parameters
        params = signature(BratCog.bratchat.callback).parameters
        param_names = [p for p in params if p not in ("self", "interaction")]

        assert "brat_level" not in param_names
        assert "message" in param_names

    async def test_bratchat_returns_early_when_unverified(self) -> None:
        """bratchat returns without calling LLM when age gate returns False."""
        from bratbot.commands.bratchat import BratCog

        mock_bot = AsyncMock()
        mock_bot.llm_client = AsyncMock()

        cog = BratCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456

        with patch(
            "bratbot.commands.bratchat.check_age_verified", new_callable=AsyncMock
        ) as mock_gate:
            mock_gate.return_value = False
            await cog.bratchat.callback(cog, mock_interaction, message="hello")

        mock_bot.llm_client.chat.assert_not_called()
