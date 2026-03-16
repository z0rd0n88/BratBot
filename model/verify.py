"""Discord request signature verification (Ed25519)."""

import json
import os

from fastapi import HTTPException, Request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

DISCORD_PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
_verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))


async def verify_discord_request(request: Request) -> dict:
    """FastAPI dependency that verifies Discord's Ed25519 signature.

    Returns the parsed JSON body on success so the route handler
    doesn't need to re-read the already-consumed request body.
    """
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")

    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")

    body = (await request.body()).decode("utf-8")

    try:
        _verify_key.verify(
            f"{timestamp}{body}".encode(),
            bytes.fromhex(signature),
        )
    except (BadSignatureError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    return json.loads(body)
