"""Bot personality configuration — all user-facing strings and LLM endpoint for a given bot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    """All personality-specific strings and routing config for a bot instance.

    Attach an instance to the bot as ``bot.personality`` in ``setup_hook``.
    Shared cogs (``common.events.*``) read from here instead of using
    hardcoded constants, so the same event code serves any personality.
    """

    name: str
    """Human-readable bot name used in logs."""

    chat_endpoint: str
    """Model server endpoint for mention-reply LLM calls (e.g. ``"/bratchat"``)."""

    # --- messages.py strings ---
    rate_limited_reply: str
    empty_mention_reply: str
    llm_error_reply: str

    # --- errors.py strings ---
    generic_error: str
    permission_error: str
    cooldown_error: str
    not_found_error: str
    discord_rate_limit_error: str
    llm_connection_error: str
    llm_timeout_error: str
    llm_server_error: str
    llm_validation_error: str
    llm_generic_error: str
    llm_warming_up_reply: str

    # --- help.py strings ---
    help_text: str
    """Full formatted help message sent in response to /help."""
