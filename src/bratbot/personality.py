"""Bot personality configuration — all user-facing strings and LLM endpoint for a given bot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    """All personality-specific strings and routing config for a bot instance.

    Attach an instance to the bot as ``bot.personality`` in ``setup_hook``.
    Shared cogs (``bratbot.events.*``) read from here instead of using
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


BRAT_PERSONALITY = Personality(
    name="BratBot",
    chat_endpoint="/bratchat",
    # messages.py
    rate_limited_reply="Slow down. I have better things to do.",
    empty_mention_reply="You pinged me just to say nothing? Classic.",
    llm_error_reply="Something went wrong with my brain. Try again, or don't. I don't care.",
    # errors.py
    generic_error="Something broke. It's probably your fault, but I'll look into it.",
    permission_error="You don't have the permission to do that. Sad for you.",
    cooldown_error="Slow down. I'm not a machine. Well, I am, but still.",
    not_found_error="That command doesn't exist. Maybe try one that does?",
    discord_rate_limit_error="Discord told me to slow down. Try again in a sec.",
    llm_connection_error="My brain is offline. Someone probably tripped over the server cable.",
    llm_timeout_error="I lost my train of thought. Try again, I guess.",
    llm_server_error="My brain had a hiccup. Try again.",
    llm_validation_error="That doesn't make sense. Even for you.",
    llm_generic_error="Something went wrong with my thinking process. Weird.",
)
