"""Tests for the encrypted personality prompt loader and helper script.

Covers:
  - PyNaCl SecretBox crypto primitives in scripts/encrypt-prompts.py
  - The model/app.py _load_prompt() function (cache, fallback, error paths)
  - End-to-end encrypt/decrypt/verify behaviour of the helper script
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import subprocess
import sys
from pathlib import Path

import nacl.exceptions
import nacl.utils
import pytest
from nacl.secret import SecretBox

# conftest.py adds model/ to sys.path before collection
import app  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Helper script import (filename has a hyphen, so importlib is needed)
# ---------------------------------------------------------------------------
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "encrypt-prompts.py"

_spec = importlib.util.spec_from_file_location("encrypt_prompts", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
encrypt_prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(encrypt_prompts)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_key() -> tuple[bytes, str]:
    """Generate a fresh SecretBox key (raw bytes + base64-url string form)."""
    key_bytes = nacl.utils.random(SecretBox.KEY_SIZE)
    key_b64 = base64.urlsafe_b64encode(key_bytes).decode("ascii")
    return key_bytes, key_b64


@pytest.fixture
def isolated_prompt_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point app.PROMPT_DIR at a fresh temp dir and clear the prompt cache."""
    monkeypatch.setattr(app, "PROMPT_DIR", tmp_path)
    monkeypatch.setattr(app, "_PROMPT_CACHE", {})
    return tmp_path


@pytest.fixture
def disable_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove BRATBOT_TEST_MODE so the loader uses real file/decrypt path."""
    monkeypatch.delenv("BRATBOT_TEST_MODE", raising=False)


# ---------------------------------------------------------------------------
# Crypto primitives (encrypt-prompts.py)
# ---------------------------------------------------------------------------


class TestCryptoPrimitives:
    def test_encrypt_decrypt_roundtrip(self, fresh_key):
        key_bytes, _ = fresh_key
        plaintext = "Hello, this is a test prompt with emoji 🎉 and unicode ☃"
        ciphertext = encrypt_prompts.encrypt_text(plaintext, key_bytes)
        recovered = encrypt_prompts.decrypt_text(ciphertext, key_bytes)
        assert recovered == plaintext

    def test_ciphertext_is_pure_ascii(self, fresh_key):
        """Ciphertext must be ASCII so it survives Windows git checkouts."""
        key_bytes, _ = fresh_key
        ciphertext = encrypt_prompts.encrypt_text("hello", key_bytes)
        ciphertext.encode("ascii")  # raises if non-ASCII
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
        assert all(c in valid_chars for c in ciphertext)

    def test_each_encrypt_uses_fresh_nonce(self, fresh_key):
        """Same plaintext + same key must produce different ciphertexts (random nonce)."""
        key_bytes, _ = fresh_key
        c1 = encrypt_prompts.encrypt_text("hello", key_bytes)
        c2 = encrypt_prompts.encrypt_text("hello", key_bytes)
        assert c1 != c2

    def test_decrypt_with_wrong_key_raises_crypto_error(self, fresh_key):
        key_bytes, _ = fresh_key
        ciphertext = encrypt_prompts.encrypt_text("hello", key_bytes)
        wrong_key = nacl.utils.random(SecretBox.KEY_SIZE)
        with pytest.raises(nacl.exceptions.CryptoError):
            encrypt_prompts.decrypt_text(ciphertext, wrong_key)

    def test_decode_key_valid(self, fresh_key):
        _, key_b64 = fresh_key
        raw = encrypt_prompts.decode_key(key_b64)
        assert len(raw) == SecretBox.KEY_SIZE

    def test_decode_key_invalid_base64(self):
        with pytest.raises(ValueError, match="not valid base64"):
            encrypt_prompts.decode_key("not!valid!base64!@#$")

    def test_decode_key_wrong_length(self):
        too_short = base64.urlsafe_b64encode(b"too short").decode("ascii")
        with pytest.raises(ValueError, match="must decode to"):
            encrypt_prompts.decode_key(too_short)

    def test_large_plaintext_roundtrip(self, fresh_key):
        """Verify a 100KB plaintext round-trips cleanly."""
        key_bytes, _ = fresh_key
        plaintext = "x" * 100_000
        ciphertext = encrypt_prompts.encrypt_text(plaintext, key_bytes)
        assert encrypt_prompts.decrypt_text(ciphertext, key_bytes) == plaintext


# ---------------------------------------------------------------------------
# _load_prompt function in model/app.py
# ---------------------------------------------------------------------------


class TestLoadPrompt:
    def test_test_mode_returns_sentinel(self, isolated_prompt_dir, monkeypatch):
        """When BRATBOT_TEST_MODE=1, loader returns a sentinel string."""
        monkeypatch.setenv("BRATBOT_TEST_MODE", "1")
        result = app._load_prompt("anything")
        assert "test fixture" in result.lower()
        assert "anything" in result

    def test_prefers_plaintext_over_encrypted(
        self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode
    ):
        """When both .txt and .txt.enc exist, .txt wins (local-dev fast path)."""
        key_bytes, key_b64 = fresh_key
        monkeypatch.setenv("PROMPTS_ENCRYPTION_KEY", key_b64)

        plaintext_content = "this is the plaintext"
        encrypted_content = "this is what's in the .enc"

        (isolated_prompt_dir / "test.txt").write_text(plaintext_content)
        (isolated_prompt_dir / "test.txt.enc").write_text(
            encrypt_prompts.encrypt_text(encrypted_content, key_bytes)
        )

        assert app._load_prompt("test") == plaintext_content

    def test_decrypts_enc_when_plaintext_missing(
        self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode
    ):
        """Loader decrypts .txt.enc when only the encrypted file exists."""
        key_bytes, key_b64 = fresh_key
        monkeypatch.setenv("PROMPTS_ENCRYPTION_KEY", key_b64)

        original = "the original prompt content"
        (isolated_prompt_dir / "test.txt.enc").write_text(
            encrypt_prompts.encrypt_text(original, key_bytes)
        )

        assert app._load_prompt("test") == original

    def test_caches_result(self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode):
        """Repeated calls return cached value without re-reading the file."""
        _, key_b64 = fresh_key
        monkeypatch.setenv("PROMPTS_ENCRYPTION_KEY", key_b64)

        (isolated_prompt_dir / "test.txt").write_text("first")

        result1 = app._load_prompt("test")
        # Mutate the file under the loader to verify cache hit (no re-read).
        (isolated_prompt_dir / "test.txt").write_text("second")
        result2 = app._load_prompt("test")

        assert result1 == "first"
        assert result2 == "first"

    def test_strips_whitespace(
        self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode
    ):
        """Loader strips leading/trailing whitespace from prompt content."""
        _, key_b64 = fresh_key
        monkeypatch.setenv("PROMPTS_ENCRYPTION_KEY", key_b64)
        (isolated_prompt_dir / "test.txt").write_text("\n\nhello world\n\n")
        assert app._load_prompt("test") == "hello world"

    def test_missing_key_with_only_enc_raises(
        self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode
    ):
        """When only .enc exists and PROMPTS_ENCRYPTION_KEY is unset → clear error."""
        key_bytes, _ = fresh_key
        monkeypatch.delenv("PROMPTS_ENCRYPTION_KEY", raising=False)
        (isolated_prompt_dir / "test.txt.enc").write_text(
            encrypt_prompts.encrypt_text("content", key_bytes)
        )
        with pytest.raises(RuntimeError, match="PROMPTS_ENCRYPTION_KEY"):
            app._load_prompt("test")

    def test_wrong_key_raises_actionable_error(
        self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode
    ):
        """Wrong PROMPTS_ENCRYPTION_KEY produces a clear error pointing at the env var."""
        key_bytes, _ = fresh_key
        wrong_key = nacl.utils.random(SecretBox.KEY_SIZE)
        wrong_key_b64 = base64.urlsafe_b64encode(wrong_key).decode("ascii")
        monkeypatch.setenv("PROMPTS_ENCRYPTION_KEY", wrong_key_b64)
        (isolated_prompt_dir / "test.txt.enc").write_text(
            encrypt_prompts.encrypt_text("content", key_bytes)
        )
        with pytest.raises(RuntimeError, match="Failed to decrypt"):
            app._load_prompt("test")

    def test_invalid_key_format_raises(
        self, isolated_prompt_dir, fresh_key, monkeypatch, disable_test_mode
    ):
        """A non-base64 key produces a clear "not a valid base64" error."""
        key_bytes, _ = fresh_key
        monkeypatch.setenv("PROMPTS_ENCRYPTION_KEY", "not!valid!base64!@#")
        (isolated_prompt_dir / "test.txt.enc").write_text(
            encrypt_prompts.encrypt_text("content", key_bytes)
        )
        with pytest.raises(RuntimeError, match="not a valid base64"):
            app._load_prompt("test")

    def test_both_files_missing_raises(self, isolated_prompt_dir, monkeypatch, disable_test_mode):
        """When neither .txt nor .txt.enc exists → clear error."""
        monkeypatch.delenv("PROMPTS_ENCRYPTION_KEY", raising=False)
        with pytest.raises(RuntimeError, match="No prompt file found"):
            app._load_prompt("nonexistent")


# ---------------------------------------------------------------------------
# Helper script CLI subcommands (in-process and subprocess)
# ---------------------------------------------------------------------------


def _ns(**kwargs) -> argparse.Namespace:
    """Build an argparse.Namespace for testing the script's cmd_* functions."""
    return argparse.Namespace(**kwargs)


@pytest.fixture
def fake_prompts_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fake model/prompts/ directory and point the script at it."""
    prompts_dir = tmp_path / "model" / "prompts"
    prompts_dir.mkdir(parents=True)
    monkeypatch.setattr(encrypt_prompts, "PROMPTS_DIR", prompts_dir)
    return prompts_dir


class TestEncryptScriptCommands:
    def test_keygen_via_subprocess(self):
        """End-to-end check: argparse wiring + main() works."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "keygen"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        key_b64 = result.stdout.strip()
        raw = base64.urlsafe_b64decode(key_b64)
        assert len(raw) == SecretBox.KEY_SIZE

    def test_encrypt_then_decrypt_roundtrip(self, fake_prompts_layout, fresh_key):
        """End-to-end: write plaintext → encrypt → delete → decrypt → bytes match."""
        _, key_b64 = fresh_key
        original = "the prompt content with unicode ☃ and emoji 🎉"
        (fake_prompts_layout / "test.txt").write_text(original, encoding="utf-8")

        assert encrypt_prompts.cmd_encrypt(_ns(key=key_b64)) == 0
        assert (fake_prompts_layout / "test.txt.enc").exists()

        # Delete plaintext, recover via decrypt
        (fake_prompts_layout / "test.txt").unlink()
        assert encrypt_prompts.cmd_decrypt(_ns(key=key_b64, force=False)) == 0
        assert (fake_prompts_layout / "test.txt").read_text(encoding="utf-8") == original

    def test_encrypt_is_idempotent(self, fake_prompts_layout, fresh_key):
        """Re-encrypting unchanged plaintext should leave the .enc file untouched."""
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("stable content")

        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))
        first_content = (fake_prompts_layout / "test.txt.enc").read_text()

        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))
        second_content = (fake_prompts_layout / "test.txt.enc").read_text()

        assert first_content == second_content

    def test_encrypt_re_encrypts_when_plaintext_changes(self, fake_prompts_layout, fresh_key):
        """Editing the plaintext should produce a different .enc on next encrypt."""
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("first version")

        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))
        first_content = (fake_prompts_layout / "test.txt.enc").read_text()

        (fake_prompts_layout / "test.txt").write_text("second version")
        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))
        second_content = (fake_prompts_layout / "test.txt.enc").read_text()

        assert first_content != second_content

    def test_decrypt_refuses_to_overwrite_without_force(self, fake_prompts_layout, fresh_key):
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("original")
        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))

        # Simulate local edits the developer hasn't re-encrypted yet.
        local_edit = "LOCAL EDITED - should not be overwritten"
        (fake_prompts_layout / "test.txt").write_text(local_edit)

        rc = encrypt_prompts.cmd_decrypt(_ns(key=key_b64, force=False))
        assert rc == 0
        # Local working copy preserved
        assert (fake_prompts_layout / "test.txt").read_text() == local_edit

    def test_decrypt_force_overwrites(self, fake_prompts_layout, fresh_key):
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("the canonical content")
        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))
        (fake_prompts_layout / "test.txt").write_text("local junk")

        rc = encrypt_prompts.cmd_decrypt(_ns(key=key_b64, force=True))
        assert rc == 0
        assert (fake_prompts_layout / "test.txt").read_text() == "the canonical content"

    def test_verify_succeeds_when_in_sync(self, fake_prompts_layout, fresh_key):
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("synced content")
        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))

        rc = encrypt_prompts.cmd_verify(
            _ns(key=key_b64, path=str(fake_prompts_layout / "test.txt.enc"))
        )
        assert rc == 0

    def test_verify_detects_drift(self, fake_prompts_layout, fresh_key):
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("original")
        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))

        # Edit plaintext without re-encrypting
        (fake_prompts_layout / "test.txt").write_text("edited but not re-encrypted")

        rc = encrypt_prompts.cmd_verify(
            _ns(key=key_b64, path=str(fake_prompts_layout / "test.txt.enc"))
        )
        assert rc == 3

    def test_verify_accepts_txt_path_too(self, fake_prompts_layout, fresh_key):
        """verify should normalize either the .txt or the .txt.enc path."""
        _, key_b64 = fresh_key
        (fake_prompts_layout / "test.txt").write_text("synced content")
        encrypt_prompts.cmd_encrypt(_ns(key=key_b64))

        rc = encrypt_prompts.cmd_verify(
            _ns(key=key_b64, path=str(fake_prompts_layout / "test.txt"))
        )
        assert rc == 0
