"""Age verification gate — guard function, reply helper, and VerificationView."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from bratbot.bot import BratBot

DISCLAIMER_TEMPLATE = (
    "\u26a0\ufe0f **Content Warning** \u2014 This bot is unfiltered and contains graphic "
    "and sexual content. By clicking below you confirm you are 18 or older "
    "and agree to our [Terms of Service]({terms_url}) and "
    "[Privacy Policy]({privacy_url})."
)


async def _reply(interaction: discord.Interaction, content: str, ephemeral: bool = False) -> None:
    """Send a response, choosing followup or send_message based on interaction state."""
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(content, ephemeral=ephemeral)


async def check_age_verified(
    interaction: discord.Interaction,
    bot: BratBot,
    callback_fn: Callable[[discord.Interaction], Coroutine[Any, Any, None]],
) -> bool:
    """Check if user is age-verified; if not, show verification prompt.

    Returns True if already verified (caller should proceed).
    Returns False if unverified (View was sent, caller should return).
    """
    if await bot.age_verification_store.is_verified(interaction.user.id):
        return True

    from bratbot.config import settings  # deferred to call time for test isolation

    disclaimer = DISCLAIMER_TEMPLATE.format(
        terms_url=settings.terms_url, privacy_url=settings.privacy_url
    )
    await interaction.response.send_message(
        disclaimer, view=VerificationView(bot, callback_fn), ephemeral=True
    )
    return False


class VerificationView(discord.ui.View):
    """Ephemeral view with a single age verification button."""

    def __init__(
        self,
        bot: BratBot,
        callback_fn: Callable[[discord.Interaction], Coroutine[Any, Any, None]],
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.callback_fn = callback_fn

    @discord.ui.button(
        label="I confirm I am 18 or older",
        style=discord.ButtonStyle.success,
        emoji="\u2705",
    )
    async def confirm_button(
        self, button_interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if button.disabled:
            return
        button.disabled = True
        self.stop()
        await button_interaction.response.defer(ephemeral=True)
        await self.bot.age_verification_store.set_verified(button_interaction.user.id)
        await button_interaction.followup.send("\u2705 Verified! Let me get that for you...")
        await self.callback_fn(button_interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
