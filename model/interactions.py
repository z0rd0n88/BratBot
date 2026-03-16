"""Discord Interactions endpoint (HTTP-based)."""

import logging

from fastapi import APIRouter, Depends

from verify import verify_discord_request

logger = logging.getLogger("bratbot-model")

interactions_router = APIRouter()

# Discord interaction types
_PING = 1
_APPLICATION_COMMAND = 2
_MESSAGE_COMPONENT = 3

# Discord interaction callback types
_PONG = 1
_DEFERRED_CHANNEL_MESSAGE = 5


@interactions_router.post("/interactions")
async def handle_interaction(body: dict = Depends(verify_discord_request)):
    """Receive and route Discord interactions.

    All requests are signature-verified by the verify_discord_request dependency
    before reaching this handler.
    """
    interaction_type = body.get("type")

    # Type 1: PING — Discord sends this to validate the endpoint URL
    if interaction_type == _PING:
        logger.info("discord_ping_received")
        return {"type": _PONG}

    # Type 2/3: Application commands and components — defer for now
    logger.info(
        "interaction_received type=%d id=%s",
        interaction_type,
        body.get("id", "unknown"),
    )
    return {"type": _DEFERRED_CHANNEL_MESSAGE}
