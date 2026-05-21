import base64
import hashlib
import hmac
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet


def _secret_material() -> str:
    secret = (
        os.getenv("LLM_CONFIG_ENCRYPTION_KEY")
        or os.getenv("SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
    )
    if not secret:
        raise RuntimeError(
            "LLM config encryption requires LLM_CONFIG_ENCRYPTION_KEY, SECRET_KEY, or JWT_SECRET_KEY"
        )
    return secret


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    digest = hashlib.sha256(_secret_material().encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_text(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    token = _fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    token = str(value).encode("utf-8")
    plaintext = _fernet().decrypt(token)
    return plaintext.decode("utf-8")


def mask_secret(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    secret = str(value)
    if len(secret) <= 6:
        return "*" * len(secret)
    return f"{secret[:3]}...{secret[-3:]}"


def hmac_text(value: Optional[str]) -> Optional[str]:
    """Return a deterministic HMAC-SHA256 hex digest of value.

    Used to index encrypted fields so we can do DB lookups without decrypting.
    The digest is keyed with SECRET_KEY (or fallback) so it cannot be brute-forced
    from outside the system.
    """
    if value in (None, ""):
        return None
    key = _secret_material().encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()