"""Unit tests for router.auth."""
import os

import pytest
from fastapi import Request
from starlette.datastructures import Headers

# Import after env is set by conftest (ROUTER_CLIENT_KEY, ROUTER_ADMIN_KEY)
from router import auth


def test_get_session_id_from_header():
    """Session ID from X-Router-Session-Id header."""
    req = Request(scope={"type": "http", "headers": [(b"x-router-session-id", b"my-session-123")]})
    assert auth.get_session_id(req) == "my-session-123"


def test_get_session_id_from_bearer_hash():
    """Session ID from hash of Bearer token when no X-Router-Session-Id."""
    req = Request(scope={"type": "http", "headers": [(b"authorization", b"Bearer some-token")]})
    sid = auth.get_session_id(req)
    assert len(sid) == 64
    assert sid == auth.get_session_id(req)  # deterministic


def test_get_session_id_anonymous():
    """Session ID for request without auth is hash of 'anonymous'."""
    req = Request(scope={"type": "http", "headers": []})
    sid = auth.get_session_id(req)
    assert len(sid) == 64


@pytest.mark.asyncio
async def test_require_client_key_valid():
    """require_client_key accepts correct Bearer token."""
    req = Request(scope={"type": "http", "headers": [(b"authorization", b"Bearer test-client-key")]})
    from fastapi.security import HTTPAuthorizationCredentials
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-client-key")
    result = await auth.require_client_key(req, creds)
    assert result == "test-client-key"


@pytest.mark.asyncio
async def test_require_client_key_invalid():
    """require_client_key rejects wrong token."""
    from fastapi import HTTPException
    req = Request(scope={"type": "http", "headers": []})
    creds = None
    with pytest.raises(HTTPException) as exc:
        await auth.require_client_key(req, creds)
    assert exc.value.status_code == 401
    assert "invalid_api_key" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_require_admin_key_bearer():
    """require_admin_key accepts Bearer ROUTER_ADMIN_KEY."""
    req = Request(scope={"type": "http", "headers": [(b"authorization", b"Bearer test-admin-key")]})
    from fastapi.security import HTTPAuthorizationCredentials
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-admin-key")
    result = await auth.require_admin_key(req, creds, None)
    assert result == "test-admin-key"


@pytest.mark.asyncio
async def test_require_admin_key_x_api_key():
    """require_admin_key accepts X-API-Key header."""
    req = Request(scope={"type": "http", "headers": [(b"x-api-key", b"test-admin-key")]})
    result = await auth.require_admin_key(req, None, "test-admin-key")
    assert result == "test-admin-key"


def test_openai_error_401_shape():
    """_openai_error_401 returns OpenAI-style error dict."""
    d = auth._openai_error_401("custom message")
    assert d["error"]["message"] == "custom message"
    assert d["error"]["type"] == "invalid_request_error"
    assert d["error"]["code"] == "invalid_api_key"
