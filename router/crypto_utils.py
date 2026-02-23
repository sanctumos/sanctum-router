"""
Credential encryption for provider API keys. ROUTER_ENCRYPTION_KEY from env.
Encrypt before write to providers.api_key_encrypted; decrypt only in memory when calling provider.
Never log or return decrypted keys. PRD §12 Persistence & secrets.

Key derivation: PBKDF2-HMAC-SHA256 with a fixed salt (no per-key salt stored). Key rotation is not
automatic: changing ROUTER_ENCRYPTION_KEY requires re-encrypting all provider API keys (e.g. via
admin PATCH with the new key set); existing ciphertexts cannot be decrypted with a new key.
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_encryption_key() -> Optional[bytes]:
    raw = os.environ.get("ROUTER_ENCRYPTION_KEY")
    if not raw or len(raw) < 16:
        return None
    # Derive a 32-byte key suitable for Fernet (AES-128-CBC + HMAC)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"sanctum-router-db", iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(raw.encode("utf-8") if isinstance(raw, str) else raw))


def encryption_available() -> bool:
    """Return True if ROUTER_ENCRYPTION_KEY is set and valid (min 16 chars). Use before storing API keys."""
    return _get_encryption_key() is not None


def encrypt_api_key(plaintext: Optional[str]) -> Optional[bytes]:
    if plaintext is None or plaintext == "":
        return None
    key = _get_encryption_key()
    if key is None:
        return None
    f = Fernet(key)
    return f.encrypt(plaintext.encode("utf-8"))


def decrypt_api_key(encrypted: Optional[bytes]) -> Optional[str]:
    if encrypted is None or len(encrypted) == 0:
        return None
    key = _get_encryption_key()
    if key is None:
        return None
    try:
        f = Fernet(key)
        return f.decrypt(encrypted).decode("utf-8")
    except InvalidToken:
        return None
