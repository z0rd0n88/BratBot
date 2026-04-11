"""Bot personality configuration — all user-facing strings and LLM endpoint for a given bot."""

from __future__ import annotations

from common.personality import Personality  # noqa: F401

_BRAT_HELP = """\
**BratBot Commands** \N{EM DASH} since you clearly couldn't figure it out yourself.

`/bratchat <message>` \N{EM DASH} send me a message and I'll respond. Try to make it interesting.
`/camichat <message>` \N{EM DASH} chat with Cami instead. She's more patient than I am.
`/verbose [1-3]` \N{EM DASH} set response length (1=short, 2=medium, 3=long). Omit to view current.
`/pronoun [choice]` \N{EM DASH} set how Cami addresses you (male/female/other).
`/ping` \N{EM DASH} check that I'm alive. I am.

[Privacy Policy](https://z0rd0n88.github.io/BratBot/privacy) \N{EM DASH} [Terms of Service](https://z0rd0n88.github.io/BratBot/terms)\
"""


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
    llm_warming_up_reply="My brain's still booting up. Give it a minute, genius.",
    # help.py
    help_text=_BRAT_HELP,
)
