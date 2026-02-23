"""
Authentication and session correlation. PRD § Config API, §6 Config API.
- /v1/*: ROUTER_CLIENT_KEY (Bearer). Allow unauthenticated if keys not set (dev only).
- /admin/*: ROUTER_ADMIN_KEY (Bearer or X-API-Key). Return 401 with OpenAI-style error when missing/invalid.
- get_session_id(request): X-Router-Session-Id or hash(Authorization Bearer).
"""

import hashlib
import os
from typing import Optional

from fastapi import Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader


CLIENT_KEY = os.environ.get("ROUTER_CLIENT_KEY")
ADMIN_KEY = os.environ.get("ROUTER_ADMIN_KEY")

# Allow unauthenticated when keys not set (dev only; document prod must set keys)
ALLOW_ANON_DEV = not CLIENT_KEY and not ADMIN_KEY

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def _openai_error_401(message: str = "Invalid or missing authentication") -> dict:
    return {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": "invalid_api_key",
        }
    }


async def require_client_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    """Dependency for /v1/*: require Bearer ROUTER_CLIENT_KEY, or allow anon in dev if no keys set."""
    if ALLOW_ANON_DEV:
        return None
    if not CLIENT_KEY:
        raise HTTPException(status_code=401, detail=_openai_error_401("ROUTER_CLIENT_KEY not configured"))
    token = None
    if credentials:
        token = credentials.credentials
    if token != CLIENT_KEY:
        raise HTTPException(status_code=401, detail=_openai_error_401())
    return token


async def require_admin_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_scheme),
) -> Optional[str]:
    """Dependency for /admin/*: require Bearer ROUTER_ADMIN_KEY or X-API-Key: ROUTER_ADMIN_KEY."""
    if ALLOW_ANON_DEV:
        return None
    if not ADMIN_KEY:
        raise HTTPException(status_code=401, detail=_openai_error_401("ROUTER_ADMIN_KEY not configured"))
    token = None
    if credentials:
        token = credentials.credentials
    if api_key and api_key == ADMIN_KEY:
        token = api_key
    if token != ADMIN_KEY:
        raise HTTPException(status_code=401, detail=_openai_error_401())
    return token


def get_session_id(request: Request) -> str:
    """
    Session ID for override correlation: X-Router-Session-Id if present,
    else hash(Authorization Bearer token). PRD § Session correlation.
    """
    session_header = request.headers.get("X-Router-Session-Id")
    if session_header:
        return session_header.strip()
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return hashlib.sha256(token.encode()).hexdigest()
    return hashlib.sha256(b"anonymous").hexdigest()
