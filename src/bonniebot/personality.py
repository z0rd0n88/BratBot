"""BonnieBot personality — fill in these strings before first deployment."""

from bratbot.personality import Personality

BONNIE_PERSONALITY = Personality(
    name="BonnieBot",
    chat_endpoint="/bonniebot",
    # messages.py
    rate_limited_reply=(
        "Easy there, sweetheart. I like eagerness, but you've gotta earn the next round."
    ),
    empty_mention_reply=(
        "You pinged me with nothing to say? That's okay, honey bun"
        " \N{EM DASH} most people are speechless around me."
    ),
    llm_error_reply=(
        "Something short-circuited in my head, baby cakes."
        " Try again \N{EM DASH} I promise I'm worth the wait."
    ),
    # errors.py
    generic_error=(
        "Well, something just went sideways, my darling. Don't worry, I always land on top."
    ),
    permission_error=(
        "That's above your clearance, sweetheart. This area is for experienced riders only."
    ),
    cooldown_error=(
        "Patience, honey bun. Good things come to those who wait"
        " \N{EM DASH} and I am a very good thing."
    ),
    not_found_error="That command doesn't exist, baby cakes. Maybe try one that does? I'll wait.",
    discord_rate_limit_error=(
        "Discord's making me take a breather, my darling. Even I need a cooldown between rounds."
    ),
    llm_connection_error=(
        "My brain's taking a little nap, sweetheart. Someone wake it up \N{EM DASH} gently, or not."
    ),
    llm_timeout_error="I got distracted thinking about... things. Try again, honey bun.",
    llm_server_error=(
        "My brain had a moment, baby cakes."
        " Give me another shot \N{EM DASH} I rarely disappoint twice."
    ),
    llm_validation_error=(
        "That didn't make sense, my darling. Try again with something I can actually work with."
    ),
    llm_generic_error=(
        "Something went wrong upstairs, sweetheart. I'm usually much more put together than this."
    ),
)
