"""Tests for age verification gate — guard function and VerificationView."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest


class TestCheckAgeVerified:
    async def test_verified_user_returns_true(self) -> None:
        from bratbot.utils.age_gate import check_age_verified

        mock_bot = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=True)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        callback_fn = AsyncMock()

        result = await check_age_verified(mock_interaction, mock_bot, callback_fn)

        assert result is True
        mock_interaction.response.send_message.assert_not_called()

    @patch("bratbot.utils.age_gate.VerificationView")
    async def test_unverified_user_sends_view_returns_false(self, mock_view_cls) -> None:
        from bratbot.utils.age_gate import check_age_verified

        mock_bot = AsyncMock()
        mock_bot.age_verification_store.is_verified = AsyncMock(return_value=False)
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456
        callback_fn = AsyncMock()

        result = await check_age_verified(mock_interaction, mock_bot, callback_fn)

        assert result is False
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        assert call_kwargs["ephemeral"] is True
        assert "view" in call_kwargs


class TestReplyHelper:
    async def test_reply_uses_send_message_when_not_done(self) -> None:
        from bratbot.utils.age_gate import _reply

        mock_interaction = AsyncMock()
        mock_interaction.response.is_done = MagicMock(return_value=False)

        await _reply(mock_interaction, "test message", ephemeral=True)

        mock_interaction.response.send_message.assert_called_once_with(
            "test message", ephemeral=True
        )
        mock_interaction.followup.send.assert_not_called()

    async def test_reply_uses_followup_when_done(self) -> None:
        from bratbot.utils.age_gate import _reply

        mock_interaction = AsyncMock()
        mock_interaction.response.is_done = MagicMock(return_value=True)

        await _reply(mock_interaction, "test message", ephemeral=True)

        mock_interaction.followup.send.assert_called_once_with(
            "test message", ephemeral=True
        )
        mock_interaction.response.send_message.assert_not_called()


class TestVerificationView:
    async def test_button_click_verifies_user_and_calls_callback(self) -> None:
        from bratbot.utils.age_gate import VerificationView

        mock_bot = AsyncMock()
        callback_fn = AsyncMock()
        view = VerificationView(mock_bot, callback_fn)

        # Get the actual button from view children
        button = view.children[0]
        assert not button.disabled

        # Simulate button interaction via the button's callback
        button_interaction = AsyncMock()
        button_interaction.user.id = 123456
        await button.callback(button_interaction)

        # Verify: button disabled, deferred, verified, callback called
        assert button.disabled is True
        button_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_bot.age_verification_store.set_verified.assert_called_once_with(123456)
        callback_fn.assert_called_once_with(button_interaction)

    async def test_double_click_is_noop(self) -> None:
        from bratbot.utils.age_gate import VerificationView

        mock_bot = AsyncMock()
        callback_fn = AsyncMock()
        view = VerificationView(mock_bot, callback_fn)

        # Pre-disable the button to simulate already-clicked state
        button = view.children[0]
        button.disabled = True

        button_interaction = AsyncMock()
        await button.callback(button_interaction)

        # Nothing should happen
        button_interaction.response.defer.assert_not_called()
        mock_bot.age_verification_store.set_verified.assert_not_called()
        callback_fn.assert_not_called()

    async def test_timeout_disables_children(self) -> None:
        from bratbot.utils.age_gate import VerificationView

        mock_bot = AsyncMock()
        callback_fn = AsyncMock()
        view = VerificationView(mock_bot, callback_fn)

        # Add a mock child
        mock_child = MagicMock()
        mock_child.disabled = False
        view._children = [mock_child]

        await view.on_timeout()

        assert mock_child.disabled is True
