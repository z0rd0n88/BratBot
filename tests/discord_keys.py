"""Shared test keypair for Discord signature verification tests."""

from nacl.signing import SigningKey

# Generate a test keypair — the private key signs, the public key verifies.
# Shared across test modules so verify.py caches the correct key at import time.
signing_key = SigningKey.generate()
verify_hex = signing_key.verify_key.encode().hex()
