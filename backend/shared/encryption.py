"""
AES-256-GCM helpers for sensitive payroll fields (SIN).

Usage:
    from shared.encryption import encrypt_sin, decrypt_sin, sin_last4

Environment:
    PAYROLL_ENCRYPTION_KEY — 32-byte (256-bit) key encoded as base64.
    Generate with: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

Raises ValueError when the env var is missing or malformed.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_ENV_KEY = "PAYROLL_ENCRYPTION_KEY"
_NONCE_BYTES = 12   # 96-bit nonce for AES-GCM


def _get_key() -> bytes:
    raw = os.environ.get(_ENV_KEY, "")
    if not raw:
        raise ValueError(
            f"Environment variable {_ENV_KEY} is not set. "
            "Generate one with: python -c \"import secrets,base64; "
            "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise ValueError(f"{_ENV_KEY} is not valid base64: {exc}") from exc
    if len(key) != 32:
        raise ValueError(
            f"{_ENV_KEY} must decode to exactly 32 bytes (256 bits), got {len(key)}."
        )
    return key


def encrypt_sin(sin: str) -> str:
    """
    Encrypt a SIN string with AES-256-GCM.

    Returns a base64-encoded string: <12-byte nonce> || <ciphertext+tag>
    """
    if not sin:
        raise ValueError("SIN must not be empty.")
    key = _get_key()
    nonce = os.urandom(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, sin.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_sin(ciphertext: str) -> str:
    """
    Decrypt a SIN previously encrypted with encrypt_sin().

    Returns the plaintext SIN string.
    """
    if not ciphertext:
        raise ValueError("Ciphertext must not be empty.")
    key = _get_key()
    raw = base64.b64decode(ciphertext)
    if len(raw) < _NONCE_BYTES + 1:
        raise ValueError("Ciphertext is too short to contain a valid nonce + tag.")
    nonce, ct = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ct, None)
    return plaintext.decode("utf-8")


def sin_last4(sin: str) -> str:
    """Return the last 4 digits of a SIN for display purposes."""
    digits = "".join(c for c in sin if c.isdigit())
    if len(digits) < 4:
        raise ValueError("SIN must contain at least 4 digits.")
    return digits[-4:]
