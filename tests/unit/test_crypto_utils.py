"""Unit tests for router.crypto_utils."""
import os

import pytest

from router import crypto_utils


def test_encrypt_decrypt_roundtrip():
    """Encrypt then decrypt returns original (with ROUTER_ENCRYPTION_KEY set)."""
    enc = crypto_utils.encrypt_api_key("secret-key")
    assert enc is not None
    assert isinstance(enc, bytes)
    dec = crypto_utils.decrypt_api_key(enc)
    assert dec == "secret-key"


def test_encrypt_none_empty():
    """encrypt_api_key returns None for None and empty string."""
    assert crypto_utils.encrypt_api_key(None) is None
    assert crypto_utils.encrypt_api_key("") is None


def test_decrypt_none_empty():
    """decrypt_api_key returns None for None and empty bytes."""
    assert crypto_utils.decrypt_api_key(None) is None
    assert crypto_utils.decrypt_api_key(b"") is None


def test_decrypt_invalid_token():
    """decrypt_api_key returns None for invalid/corrupt ciphertext."""
    assert crypto_utils.decrypt_api_key(b"not-valid-fernet-token") is None


def test_encrypt_no_key_returns_none():
    """When ROUTER_ENCRYPTION_KEY is unset or too short, encrypt returns None."""
    prev = os.environ.pop("ROUTER_ENCRYPTION_KEY", None)
    try:
        os.environ.pop("ROUTER_ENCRYPTION_KEY", None)
        assert crypto_utils.encrypt_api_key("x") is None
        os.environ["ROUTER_ENCRYPTION_KEY"] = "short"
        assert crypto_utils.encrypt_api_key("x") is None
    finally:
        if prev is not None:
            os.environ["ROUTER_ENCRYPTION_KEY"] = prev
