"""BonnieBot personality — fill in these strings before first deployment."""

from bratbot.personality import Personality

BONNIE_PERSONALITY = Personality(
    name="BonnieBot",
    chat_endpoint="/bonniebot",
    # messages.py
    rate_limited_reply="TODO: Bonnie rate-limit reply",
    empty_mention_reply="TODO: Bonnie empty-mention reply",
    llm_error_reply="TODO: Bonnie LLM error reply",
    # errors.py
    generic_error="TODO: Bonnie generic error",
    permission_error="TODO: Bonnie permission error",
    cooldown_error="TODO: Bonnie cooldown error",
    not_found_error="TODO: Bonnie not-found error",
    discord_rate_limit_error="TODO: Bonnie Discord rate-limit error",
    llm_connection_error="TODO: Bonnie LLM connection error",
    llm_timeout_error="TODO: Bonnie LLM timeout error",
    llm_server_error="TODO: Bonnie LLM server error",
    llm_validation_error="TODO: Bonnie LLM validation error",
    llm_generic_error="TODO: Bonnie LLM generic error",
)
