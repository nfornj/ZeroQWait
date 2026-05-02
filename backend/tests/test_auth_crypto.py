"""
Unit tests for shared/auth_utils.py password hashing and JWT token creation.

Covers:
  - verify_password / get_password_hash (bcrypt round-trip)
  - create_access_token (JWT encoding and expiry logic)

No live database or network required.
"""
import sys
import os
import pytest
from datetime import timedelta, datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")

from shared.auth_utils import verify_password, get_password_hash, create_access_token, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from jose import jwt


class TestPasswordHashing:
    """Tests for get_password_hash and verify_password."""

    def test_hash_is_not_plaintext(self):
        hashed = get_password_hash("mysecret")
        assert hashed != "mysecret"

    def test_hash_is_string(self):
        hashed = get_password_hash("mysecret")
        assert isinstance(hashed, str)

    def test_bcrypt_prefix(self):
        hashed = get_password_hash("test")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_correct_password_returns_true(self):
        hashed = get_password_hash("correct-password")
        assert verify_password("correct-password", hashed) is True

    def test_verify_wrong_password_returns_false(self):
        hashed = get_password_hash("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_verify_empty_password_returns_false(self):
        hashed = get_password_hash("correct-password")
        assert verify_password("", hashed) is False

    def test_verify_none_plain_returns_false(self):
        hashed = get_password_hash("correct-password")
        assert verify_password(None, hashed) is False

    def test_verify_none_hash_returns_false(self):
        assert verify_password("correct-password", None) is False

    def test_verify_both_none_returns_false(self):
        assert verify_password(None, None) is False

    def test_different_passwords_produce_different_hashes(self):
        h1 = get_password_hash("pass1")
        h2 = get_password_hash("pass2")
        assert h1 != h2

    def test_same_password_different_hashes(self):
        """bcrypt uses random salt so two hashes of the same password are different."""
        h1 = get_password_hash("same-pass")
        h2 = get_password_hash("same-pass")
        assert h1 != h2
        # But both verify correctly.
        assert verify_password("same-pass", h1)
        assert verify_password("same-pass", h2)


class TestCreateAccessToken:
    """Tests for create_access_token."""

    def test_returns_string(self):
        token = create_access_token({"sub": "testuser"})
        assert isinstance(token, str)

    def test_token_is_decodable(self):
        secret = os.environ["SECRET_KEY"]
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_default_expiry_is_set(self):
        secret = os.environ["SECRET_KEY"]
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_custom_expiry_respected(self):
        secret = os.environ["SECRET_KEY"]
        before = datetime.utcnow()
        token = create_access_token({"sub": "u"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        expiry = datetime.utcfromtimestamp(payload["exp"])
        after = datetime.utcnow() + timedelta(minutes=5, seconds=5)
        assert expiry > before
        assert expiry <= after

    def test_data_preserved_in_token(self):
        secret = os.environ["SECRET_KEY"]
        data = {"sub": "alice", "role": "shop_owner", "shop_id": 7}
        token = create_access_token(data)
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        assert payload["sub"] == "alice"
        assert payload["role"] == "shop_owner"
        assert payload["shop_id"] == 7

    def test_default_expiry_close_to_constant(self):
        """Token should expire approximately ACCESS_TOKEN_EXPIRE_MINUTES from now."""
        secret = os.environ["SECRET_KEY"]
        token = create_access_token({"sub": "u"})
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        expiry = datetime.utcfromtimestamp(payload["exp"])
        expected = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        delta = abs((expiry - expected).total_seconds())
        assert delta < 10, f"Expiry off by {delta}s from expected {ACCESS_TOKEN_EXPIRE_MINUTES}min"

    def test_invalid_secret_does_not_decode(self):
        from jose import JWTError
        token = create_access_token({"sub": "u"})
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret", algorithms=[ALGORITHM])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
