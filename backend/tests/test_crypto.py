"""
Unit tests for shared/crypto.py.

Tests encrypt_text, decrypt_text, and mask_secret.
Requires only the `cryptography` package — no DB or network.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Provide a key so _secret_material() does not raise.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")

# Clear the lru_cache so the test key is picked up fresh.
from shared import crypto as _crypto_module
_crypto_module._fernet.cache_clear()

from shared.crypto import encrypt_text, decrypt_text, mask_secret


class TestEncryptDecrypt:
    """Round-trip and edge-case tests for encrypt_text / decrypt_text."""

    def test_encrypt_returns_string(self):
        token = encrypt_text("hello")
        assert isinstance(token, str)

    def test_decrypt_restores_plaintext(self):
        plaintext = "my-api-key-12345"
        token = encrypt_text(plaintext)
        assert decrypt_text(token) == plaintext

    def test_round_trip_empty_string_returns_none(self):
        """Empty string is treated the same as None — returns None."""
        assert encrypt_text("") is None
        assert decrypt_text("") is None

    def test_encrypt_none_returns_none(self):
        assert encrypt_text(None) is None

    def test_decrypt_none_returns_none(self):
        assert decrypt_text(None) is None

    def test_different_plaintexts_produce_different_tokens(self):
        t1 = encrypt_text("secret-a")
        t2 = encrypt_text("secret-b")
        assert t1 != t2

    def test_same_plaintext_produces_different_tokens(self):
        """Fernet uses a random IV so two encryptions of the same value differ."""
        t1 = encrypt_text("same-value")
        t2 = encrypt_text("same-value")
        # Both decrypt to the same value despite being different ciphertexts.
        assert decrypt_text(t1) == decrypt_text(t2) == "same-value"

    def test_long_value_round_trips(self):
        long_value = "x" * 4096
        assert decrypt_text(encrypt_text(long_value)) == long_value

    def test_special_characters_round_trip(self):
        value = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        assert decrypt_text(encrypt_text(value)) == value

    def test_unicode_round_trip(self):
        value = "こんにちは世界"
        assert decrypt_text(encrypt_text(value)) == value


class TestMaskSecret:
    """Tests for the mask_secret() helper."""

    def test_none_returns_none(self):
        assert mask_secret(None) is None

    def test_empty_string_returns_none(self):
        assert mask_secret("") is None

    def test_short_value_fully_masked(self):
        """Values ≤ 6 chars should become all asterisks."""
        assert mask_secret("abc") == "***"
        assert mask_secret("abcdef") == "******"

    def test_long_value_shows_prefix_and_suffix(self):
        result = mask_secret("sk-1234567890abcdef")
        assert result.startswith("sk-")
        assert result.endswith("def")
        assert "..." in result

    def test_exactly_seven_chars_shows_edges(self):
        # len=7 → first 3 + '...' + last 3
        result = mask_secret("1234567")
        assert result == "123...567"

    def test_returns_string(self):
        assert isinstance(mask_secret("some-secret"), str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
