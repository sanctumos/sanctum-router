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
    upstream_model_part,
    resolve_canonical_model,
)

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


async def _try_candidates(
    body: dict,
    session_id: str,
    canonical_model: str,
    no_provider_code: str,
    adapter_call: Any,
) -> tuple[Any, int, dict[str, str], str | None]:
    """Generic try-candidates loop. adapter_call(pid, endpoint, api_key, upstream_model, body, **kwargs) -> (body, status, headers)."""
    candidates, chosen_id, canonical = resolve_candidates(session_id, body.get("model", ""), body)
    if not chosen_id or not candidates:
        msg = "No available provider for this request" if no_provider_code == "no_provider" else "No available provider"
        return (
            {"error": {"message": msg, "type": "api_error", "code": no_provider_code}},
            503,
            {},
            None,
        )
    upstream_model = upstream_model_part(canonical)
    last_error = None
    last_status = 503
    for p in candidates:
        pid = p["id"]
        provider = _get_provider(pid)
        if not provider:
            continue
        api_key = decrypt_api_key(provider.get("api_key_encrypted"))
        endpoint = provider.get("endpoint", "")
        result = await adapter_call(pid, endpoint, api_key, upstream_model, body)
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


async def _try_chat_completions(
    body: dict, session_id: str, canonical_model: str
) -> tuple[Any, int, dict[str, str], str | None]:
    """Try candidates for chat; return (body_or_stream, status, headers, chosen_provider_id)."""
    async def call_chat(pid: str, endpoint: str, api_key: str | None, um: str, b: dict) -> Any:
        return await _adapter.call_chat_completions(pid, endpoint, api_key, um, b, b.get("stream", False))
    return await _try_candidates(body, session_id, canonical_model, "no_provider", call_chat)


def _apply_openai_headers(upstream_headers: dict[str, str], out: dict[str, str], elapsed_ms: int | None = None) -> None:
    """Echo openai-version and openai-processing-ms from upstream; set processing-ms from elapsed if missing. PRD optional headers."""
    if upstream_headers.get("openai-version"):
        out["openai-version"] = upstream_headers["openai-version"]
    if upstream_headers.get("openai-processing-ms"):
        out["openai-processing-ms"] = upstream_headers["openai-processing-ms"]
    elif elapsed_ms is not None:
        out["openai-processing-ms"] = str(elapsed_ms)


@router.post("/chat/completions")
async def post_chat_completions(request: Request):
    """POST /v1/chat/completions — route, proxy, failover; set X-Router-*; echo model; echo openai-version/openai-processing-ms."""
    try:
        body = await request.json()
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Invalid JSON", "type": "invalid_request_error", "code": "invalid_json"}},
        )
    session_id = get_session_id(request)
    model = body.get("model", "")
    canonical = resolve_canonical_model(model)
    t0 = time.perf_counter()
    result_body, status, headers, provider_id = await _try_chat_completions(body, session_id, canonical)
    elapsed_ms = int((time.perf_counter() - t0) * 1000) if status < 400 else None
    _apply_openai_headers(headers, headers, elapsed_ms)
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
    """Try candidates for embeddings; return (body, status, headers, chosen_provider_id)."""
    async def call_emb(pid: str, endpoint: str, api_key: str | None, um: str, b: dict) -> Any:
        return await _adapter.call_embeddings(pid, endpoint, api_key, um, b)
    return await _try_candidates(body, session_id, canonical_model, "no_provider", call_emb)


@router.post("/embeddings")
async def post_embeddings(request: Request):
    """POST /v1/embeddings — route, proxy, failover; set X-Router-*; echo model; echo openai-version/openai-processing-ms."""
    try:
        body = await request.json()
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Invalid JSON", "type": "invalid_request_error", "code": "invalid_json"}},
        )
    session_id = get_session_id(request)
    model = body.get("model", "")
    canonical = resolve_canonical_model(model)
    t0 = time.perf_counter()
    result_body, status, headers, _ = await _try_embeddings(body, session_id, canonical)
    elapsed_ms = int((time.perf_counter() - t0) * 1000) if status < 400 else None
    _apply_openai_headers(headers, headers, elapsed_ms)
    return JSONResponse(content=result_body, status_code=status, headers=dict(headers))
