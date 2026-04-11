"""Tests for modified /bratchat command — no brat_level parameter."""

from __future__ import annotations

from inspect import signature
from unittest.mock import AsyncMock, MagicMock, patch


class TestBratChatModified:
    """Test the modified /bratchat command without brat_level parameter."""

    async def test_bratchat_fetches_user_intensity(self) -> None:
        """bratchat fetches user's stored intensity before calling LLM."""
        from bratbot.commands.bratchat import BratCog
        from common.services.rate_limiter import RateLimiter
        from common.services.request_queue import RequestQueue

        mock_bot = AsyncMock()
        mock_bot.rate_limiter = AsyncMock(spec=RateLimiter)
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.request_queue = AsyncMock(spec=RequestQueue)

        mock_bot.intensity_store = AsyncMock()
        mock_bot.intensity_store.get_intensity = AsyncMock(return_value=2)

        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        # Mock LLM client
        mock_bot.llm_client = AsyncMock()
        mock_bot.llm_client.chat = AsyncMock(
            return_value={"request_id": "test", "reply": "response"}
        )

        cog = BratCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.guild_id = None
        mock_interaction.channel = None
        mock_interaction.response.is_done = MagicMock(return_value=False)

        # Call without brat_level parameter
        await cog.bratchat.callback(cog, mock_interaction, message="hello")

        # Verify stored intensity was fetched
        mock_bot.intensity_store.get_intensity.assert_called_once_with(123456)

    async def test_bratchat_uses_default_intensity_when_not_set(self) -> None:
        """bratchat uses default intensity (3) when user hasn't set preference."""
        from bratbot.commands.bratchat import BratCog
        from common.services.rate_limiter import RateLimiter

        mock_bot = AsyncMock()
        mock_bot.rate_limiter = AsyncMock(spec=RateLimiter)
        mock_bot.rate_limiter.check_user = AsyncMock(return_value=True)
        mock_bot.rate_limiter.check_channel = AsyncMock(return_value=True)
        mock_bot.request_queue = AsyncMock()

        mock_bot.intensity_store = AsyncMock()
        # get_intensity now always returns an int (3 by default if not set)
        mock_bot.intensity_store.get_intensity = AsyncMock(return_value=3)

        mock_bot.age_verification_store = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)

        mock_bot.llm_client = AsyncMock()
        mock_bot.llm_client.chat = AsyncMock(
            return_value={"request_id": "test", "reply": "response"}
        )

        cog = BratCog(mock_bot)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        mock_interaction.guild_id = None
        mock_interaction.channel = None
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await cog.bratchat.callback(cog, mock_interaction, message="hello")

        # Verify LLM was called with default intensity
        mock_bot.llm_client.chat.assert_called_once()
        call_kwargs = mock_bot.llm_client.chat.call_args[1]
        assert call_kwargs["brat_level"] == 3

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
