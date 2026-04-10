#!/usr/bin/env python3
"""Encrypt or decrypt personality prompt files for BratBot.

Personality prompts in `model/prompts/*.txt` contain custom voice content that
shouldn't live in public git history. They're gitignored. To make them survive
a pod rebuild without exposing them, this script encrypts them with PyNaCl's
SecretBox (XSalsa20-Poly1305) into committed `*.txt.enc` files. The model
server decrypts them at startup using PROMPTS_ENCRYPTION_KEY from env.

Usage:
    python scripts/encrypt-prompts.py keygen
    python scripts/encrypt-prompts.py encrypt
    python scripts/encrypt-prompts.py decrypt [--force]
    python scripts/encrypt-prompts.py verify <path>

Reads PROMPTS_ENCRYPTION_KEY from env, or pass --key.

First-time setup:
    1. python scripts/encrypt-prompts.py keygen        # generate a key
    2. Add to .env: PROMPTS_ENCRYPTION_KEY=<key>
    3. python scripts/encrypt-prompts.py encrypt       # encrypt your .txt files
    4. git add model/prompts/*.txt.enc && git commit
    5. Add the same key to your RunPod pod template env vars

Edit workflow:
    1. Edit model/prompts/<name>.txt locally
    2. python scripts/encrypt-prompts.py encrypt
    3. git add model/prompts/<name>.txt.enc && git commit && git push

Fresh-clone recovery:
    1. Get PROMPTS_ENCRYPTION_KEY from your password manager
    2. Add to .env
    3. python scripts/encrypt-prompts.py decrypt
       (or just run the model server — it decrypts at startup)
"""

from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import os
import sys
from pathlib import Path

# Force UTF-8 stdio so em-dashes etc. render correctly on Windows consoles
# (default cp1252 can't encode them and produces "?" replacement chars).
for stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, OSError):
        stream.reconfigure(encoding="utf-8")

try:
    import nacl.exceptions
    import nacl.secret
    import nacl.utils
except ImportError:
    sys.stderr.write("ERROR: PyNaCl is required. Install dev deps with: uv sync --all-extras\n")
    sys.exit(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "model" / "prompts"
KEY_ENV_VAR = "PROMPTS_ENCRYPTION_KEY"


# ─── Crypto primitives ──────────────────────────────────────────────────────


def decode_key(key_b64: str) -> bytes:
    """Decode a base64 key string into 32 raw bytes. Raises ValueError on bad input."""
    try:
        raw = base64.urlsafe_b64decode(key_b64.strip())
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"key is not valid base64: {e}") from None
    if len(raw) != nacl.secret.SecretBox.KEY_SIZE:
        raise ValueError(
            f"key must decode to {nacl.secret.SecretBox.KEY_SIZE} bytes, got {len(raw)}"
        )
    return raw


def encrypt_text(plaintext: str, key_bytes: bytes) -> str:
    """Encrypt UTF-8 text with SecretBox; return base64-encoded ciphertext.

    Round-trip-verifies before returning as cheap insurance against PyNaCl bugs.
    """
    box = nacl.secret.SecretBox(key_bytes)
    ciphertext = box.encrypt(plaintext.encode("utf-8"))
    decrypted = box.decrypt(ciphertext).decode("utf-8")
    if decrypted != plaintext:
        raise RuntimeError(
            "round-trip verification failed: decrypted ciphertext does not "
            "match original plaintext (this should be impossible)"
        )
    return base64.b64encode(bytes(ciphertext)).decode("ascii")


def decrypt_text(b64_ciphertext: str, key_bytes: bytes) -> str:
    """Decode base64 ciphertext, decrypt with SecretBox, return UTF-8 text."""
    try:
        raw = base64.b64decode(b64_ciphertext.strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"ciphertext is not valid base64: {e}") from None
    box = nacl.secret.SecretBox(key_bytes)
    return box.decrypt(raw).decode("utf-8")


# ─── Helpers ────────────────────────────────────────────────────────────────


def get_key_bytes(args: argparse.Namespace) -> bytes:
    """Read the encryption key from --key flag or PROMPTS_ENCRYPTION_KEY env var."""
    key_str = args.key or os.environ.get(KEY_ENV_VAR)
    if not key_str:
        sys.stderr.write(
            f"ERROR: encryption key not found. Set {KEY_ENV_VAR} env var or pass --key.\n"
            "Generate one with: python scripts/encrypt-prompts.py keygen\n"
        )
        sys.exit(2)
    try:
        return decode_key(key_str)
    except ValueError as e:
        sys.stderr.write(f"ERROR: invalid encryption key: {e}\n")
        sys.exit(2)


def find_plaintext_files() -> list[Path]:
    """Return all model/prompts/*.txt plaintext files (excludes .example, .enc)."""
    return sorted(PROMPTS_DIR.glob("*.txt"))


def find_encrypted_files() -> list[Path]:
    """Return all model/prompts/*.txt.enc encrypted files."""
    return sorted(PROMPTS_DIR.glob("*.txt.enc"))


def enc_path_for(txt_path: Path) -> Path:
    """Return the .txt.enc sibling path for a given .txt path."""
    return txt_path.parent / (txt_path.name + ".enc")


def txt_path_for(enc_path: Path) -> Path:
    """Return the .txt sibling path for a given .txt.enc path."""
    return enc_path.with_suffix("")  # strips trailing .enc


# ─── Subcommands ─────────────────────────────────────────────────────────────


def cmd_keygen(args: argparse.Namespace) -> int:
    """Generate a fresh PyNaCl SecretBox key and print it as base64."""
    key_bytes = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
    key_b64 = base64.urlsafe_b64encode(key_bytes).decode("ascii")
    print(key_b64)
    sys.stderr.write(
        "\n"
        "Generated a new 32-byte SecretBox encryption key.\n"
        "\n"
        "  1. Add to your local .env file:\n"
        f"     {KEY_ENV_VAR}={key_b64}\n"
        "\n"
        "  2. Add the SAME key to the RunPod pod template environment variables\n"
        "     (https://www.runpod.io/console/user/templates)\n"
        "\n"
        "  3. Store it in your password manager — if you lose this key, the\n"
        "     committed *.txt.enc files become unrecoverable.\n"
    )
    return 0


def cmd_encrypt(args: argparse.Namespace) -> int:
    """Encrypt all model/prompts/*.txt into committed *.txt.enc files."""
    key_bytes = get_key_bytes(args)
    plaintexts = find_plaintext_files()
    if not plaintexts:
        sys.stderr.write(f"ERROR: no plaintext .txt files found in {PROMPTS_DIR}\n")
        return 1

    written = 0
    skipped = 0
    for txt_path in plaintexts:
        enc_path = enc_path_for(txt_path)
        plaintext = txt_path.read_text(encoding="utf-8")

        # Idempotency: if existing .enc decrypts to identical content, skip.
        if enc_path.exists():
            try:
                existing = decrypt_text(enc_path.read_text(encoding="ascii"), key_bytes)
                if existing == plaintext:
                    print(f"  unchanged: {enc_path.name}")
                    skipped += 1
                    continue
            except (nacl.exceptions.CryptoError, ValueError):
                # Existing .enc is unreadable with current key — re-encrypt.
                pass

        b64 = encrypt_text(plaintext, key_bytes)
        enc_path.write_text(b64 + "\n", encoding="ascii")
        print(f"  encrypted: {enc_path.name}")
        written += 1

    print(f"\n{written} encrypted, {skipped} unchanged")
    return 0


def cmd_decrypt(args: argparse.Namespace) -> int:
    """Decrypt all model/prompts/*.txt.enc into local *.txt files."""
    key_bytes = get_key_bytes(args)
    encrypted = find_encrypted_files()
    if not encrypted:
        sys.stderr.write(f"ERROR: no encrypted .txt.enc files found in {PROMPTS_DIR}\n")
        return 1

    written = 0
    skipped = 0
    for enc_path in encrypted:
        txt_path = txt_path_for(enc_path)
        if txt_path.exists() and not args.force:
            sys.stderr.write(f"  refusing to overwrite existing {txt_path.name} (use --force)\n")
            skipped += 1
            continue
        try:
            plaintext = decrypt_text(enc_path.read_text(encoding="ascii"), key_bytes)
        except nacl.exceptions.CryptoError:
            sys.stderr.write(f"ERROR: failed to decrypt {enc_path.name} — check {KEY_ENV_VAR}\n")
            return 2
        except ValueError as e:
            sys.stderr.write(f"ERROR: {enc_path.name}: {e}\n")
            return 2
        txt_path.write_text(plaintext, encoding="utf-8")
        print(f"  decrypted: {txt_path.name}")
        written += 1

    if written:
        sys.stderr.write("\nWARNING: plaintext .txt files are gitignored. Do not commit them.\n")
    print(f"\n{written} decrypted, {skipped} skipped")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a .txt.enc decrypts to match its sibling .txt working copy.

    Used by the optional pre-commit hook to catch drift between the
    plaintext and the committed ciphertext.
    """
    key_bytes = get_key_bytes(args)
    target = Path(args.path).resolve()

    # Accept either the .txt or the .txt.enc path; normalize to .enc.
    if target.name.endswith(".txt.enc"):
        enc_path = target
        txt_path = txt_path_for(target)
    elif target.name.endswith(".txt"):
        txt_path = target
        enc_path = enc_path_for(target)
    else:
        sys.stderr.write(f"ERROR: {target.name} is neither a .txt nor a .txt.enc file\n")
        return 1

    if not enc_path.exists():
        sys.stderr.write(f"ERROR: {enc_path} does not exist\n")
        return 1
    if not txt_path.exists():
        sys.stderr.write(
            f"ERROR: working-copy {txt_path.name} does not exist — cannot verify "
            f"drift. If this is a fresh clone, run `scripts/encrypt-prompts.py "
            f"decrypt` first.\n"
        )
        return 1

    try:
        decrypted = decrypt_text(enc_path.read_text(encoding="ascii"), key_bytes)
    except nacl.exceptions.CryptoError:
        sys.stderr.write(f"ERROR: failed to decrypt {enc_path.name} — check {KEY_ENV_VAR}\n")
        return 2

    working = txt_path.read_text(encoding="utf-8")
    if decrypted != working:
        sys.stderr.write(
            f"ERROR: {enc_path.name} is out of sync with {txt_path.name} — run "
            f"`python scripts/encrypt-prompts.py encrypt`\n"
        )
        return 3

    print(f"OK: {enc_path.name} matches {txt_path.name}")
    return 0


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--key",
        help=f"Encryption key (overrides {KEY_ENV_VAR} env var)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen", help="Generate a new 32-byte SecretBox key")

    sub.add_parser(
        "encrypt",
        help="Encrypt all model/prompts/*.txt into committed .txt.enc files",
    )

    p_decrypt = sub.add_parser(
        "decrypt",
        help="Decrypt all model/prompts/*.txt.enc into local .txt files",
    )
    p_decrypt.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .txt files",
    )

    p_verify = sub.add_parser(
        "verify",
        help="Verify a .txt.enc matches its sibling .txt (used by pre-commit)",
    )
    p_verify.add_argument("path", help="Path to a .txt or .txt.enc file")

    args = parser.parse_args()

    handlers = {
        "keygen": cmd_keygen,
        "encrypt": cmd_encrypt,
        "decrypt": cmd_decrypt,
        "verify": cmd_verify,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
