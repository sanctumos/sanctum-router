"""Proxy API: /v1/* — OpenAI-compatible. Auth: ROUTER_CLIENT_KEY. No request logging to DB."""

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from router.adapters.openai_compatible import OpenAICompatibleAdapter
from router.auth import get_session_id, require_client_key
from router.crypto_utils import decrypt_api_key
from router import db
from router.routing_engine import (
    resolve_candidates,
    mark_provider_unhealthy,
    _upstream_model_part,
)
from router.routing_engine import _resolve_canonical_model

router = APIRouter(prefix="/v1", tags=["proxy"], dependencies=[Depends(require_client_key)])

_adapter = OpenAICompatibleAdapter()


def _models_from_db() -> list[dict]:
    """Build /v1/models list from DB only (no upstream call)."""
    data = []
    for p in db.provider_list():
        pid = p["id"]
        models_raw = p.get("models") or "[]"
        try:
            models = json.loads(models_raw) if isinstance(models_raw, str) else models_raw
        except Exception:
            models = []
        for m in models:
            data.append({
                "id": f"{pid}+{m}",
                "object": "model",
                "created": int(time.time()),
                "owned_by": pid,
            })
    for alias, canonical_id in db.model_aliases_get_all().items():
        data.append({
            "id": alias,
            "object": "model",
            "created": int(time.time()),
            "owned_by": canonical_id.split("+", 1)[0] if "+" in canonical_id else "router",
        })
    return data


@router.get("/models")
async def get_models():
    """GET /v1/models — from DB only."""
    return {"object": "list", "data": _models_from_db()}


def _get_provider(provider_id: str) -> dict | None:
    return db.provider_get(provider_id)


async def _try_chat_completions(
    body: dict, session_id: str, canonical_model: str
) -> tuple[Any, int, dict[str, str], str | None]:
    """Try candidates in order; return (body_or_stream, status, headers, chosen_provider_id)."""
    candidates, chosen_id, canonical = resolve_candidates(session_id, body.get("model", ""), body)
    if not chosen_id or not candidates:
        return (
            {"error": {"message": "No available provider for this request", "type": "api_error", "code": "no_provider"}},
            503,
            {},
            None,
        )
    stream = body.get("stream", False)
    upstream_model = _upstream_model_part(canonical)
    last_error = None
    last_status = 503
    for p in candidates:
        pid = p["id"]
        provider = _get_provider(pid)
        if not provider:
            continue
        key_enc = provider.get("api_key_encrypted")
        api_key = decrypt_api_key(key_enc)
        endpoint = provider.get("endpoint", "")
        result = await _adapter.call_chat_completions(
            pid, endpoint, api_key, upstream_model, body, stream
        )
        resp_body, status, out_headers = result[0], result[1], result[2]
        if status >= 400:
            mark_provider_unhealthy(pid)
            last_error = resp_body
            last_status = status
            continue
        out_headers["X-Router-Provider"] = pid
        out_headers["X-Router-Upstream-Model"] = upstream_model
        if isinstance(resp_body, dict) and "model" not in resp_body:
            resp_body["model"] = canonical_model
        elif isinstance(resp_body, dict):
            resp_body["model"] = canonical_model
        return resp_body, status, out_headers, pid
    return (
        last_error or {"error": {"message": "All providers failed", "type": "api_error", "code": "failover_exhausted"}},
        last_status,
        {},
        None,
    )


@router.post("/chat/completions")
async def post_chat_completions(request: Request):
    """POST /v1/chat/completions — route, proxy, failover; set X-Router-*; echo model."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Invalid JSON", "type": "invalid_request_error", "code": "invalid_json"}},
        )
    session_id = get_session_id(request)
    model = body.get("model", "")
    canonical = _resolve_canonical_model(model)
    result_body, status, headers, provider_id = await _try_chat_completions(body, session_id, canonical)
    if hasattr(result_body, "__aiter__"):
        async def stream_echo():
            async for chunk in result_body:
                yield chunk
        return StreamingResponse(
            stream_echo(),
            status_code=status,
            media_type="text/event-stream",
            headers=dict(headers),
        )
    return JSONResponse(content=result_body, status_code=status, headers=dict(headers))


async def _try_embeddings(
    body: dict, session_id: str, canonical_model: str
) -> tuple[dict, int, dict[str, str], str | None]:
    candidates, chosen_id, canonical = resolve_candidates(session_id, body.get("model", ""), body)
    if not chosen_id or not candidates:
        return (
            {"error": {"message": "No available provider", "type": "api_error", "code": "no_provider"}},
            503,
            {},
            None,
        )
    upstream_model = _upstream_model_part(canonical)
    last_error = None
    last_status = 503
    for p in candidates:
        pid = p["id"]
        provider = _get_provider(pid)
        if not provider:
            continue
        api_key = decrypt_api_key(provider.get("api_key_encrypted"))
        result = await _adapter.call_embeddings(
            pid, provider.get("endpoint", ""), api_key, upstream_model, body
        )
        resp_body, status, out_headers = result[0], result[1], result[2]
        if status >= 400:
            mark_provider_unhealthy(pid)
            last_error = resp_body
            last_status = status
            continue
        out_headers["X-Router-Provider"] = pid
        out_headers["X-Router-Upstream-Model"] = upstream_model
        if isinstance(resp_body, dict):
            resp_body["model"] = canonical_model
        return resp_body, status, out_headers, pid
    return (
        last_error or {"error": {"message": "All providers failed", "type": "api_error", "code": "failover_exhausted"}},
        last_status,
        {},
        None,
    )


@router.post("/embeddings")
async def post_embeddings(request: Request):
    """POST /v1/embeddings — route, proxy, failover; set X-Router-*; echo model."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Invalid JSON", "type": "invalid_request_error", "code": "invalid_json"}},
        )
    session_id = get_session_id(request)
    model = body.get("model", "")
    canonical = _resolve_canonical_model(model)
    result_body, status, headers, _ = await _try_embeddings(body, session_id, canonical)
    return JSONResponse(content=result_body, status_code=status, headers=dict(headers))
