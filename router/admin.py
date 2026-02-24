"""Config API: /admin/* — status, providers CRUD, credit, override, estimate-cost, routing-config. Auth: ROUTER_ADMIN_KEY."""

import json
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel

from router import __version__, db
from router.auth import get_session_id, require_admin_key
from router.crypto_utils import encrypt_api_key, encryption_available
from router.credit_health import get_all_credit_state, get_all_health

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])

_start_time: Optional[float] = None


def set_start_time(t: float) -> None:
    global _start_time
    _start_time = t


def uptime_seconds() -> int:
    return int(time.time() - _start_time) if _start_time else 0


@router.get("/status")
async def get_status(request: Request):
    """GET /admin/status — version, providers_healthy, uptime. current_provider is the override for the caller's session (who is calling this API), not the current provider for proxy traffic."""
    session_id = get_session_id(request)
    current_provider = db.agent_override_get(session_id)
    return {
        "status": "ok",
        "version": __version__,
        "current_provider": current_provider,
        "providers_healthy": get_all_health(),
        "uptime_seconds": uptime_seconds(),
    }


@router.get("/providers")
async def list_providers():
    """GET /admin/providers — list from DB, no decrypted keys; include supports_* and healthy from memory."""
    health = get_all_health()
    rows = db.provider_list()
    out = []
    for p in rows:
        pid = p["id"]
        out.append({
            "id": pid,
            "endpoint": p["endpoint"],
            "provider_type": p.get("provider_type", "openai_compat"),
            "models": p["models"] if isinstance(p["models"], str) else json.dumps(p.get("models") or []),
            "priority": p["priority"],
            "credit_threshold": p.get("credit_threshold"),
            "supports_tools": p.get("supports_tools", True),
            "supports_streaming": p.get("supports_streaming", True),
            "supports_multimodal": p.get("supports_multimodal", False),
            "healthy": health.get(pid, True),
        })
    return out


class ProviderCreate(BaseModel):
    id: str
    endpoint: str
    models: list[str] | str
    priority: int = 1
    credit_threshold: Optional[float] = None
    provider_type: Optional[str] = None
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_multimodal: bool = False
    api_key: Optional[str] = None


@router.post("/providers")
async def create_provider(p: ProviderCreate):
    """POST /admin/providers — allowed fields include supports_multimodal; encrypt api_key. Returns { ok, provider } per PRD."""
    models_str = p.models if isinstance(p.models, str) else json.dumps(p.models)
    if p.api_key and not encryption_available():
        raise HTTPException(
            status_code=400,
            detail="ROUTER_ENCRYPTION_KEY is required to store provider API keys. Set it (min 16 characters) and retry.",
        )
    enc = encrypt_api_key(p.api_key) if p.api_key else None
    db.provider_insert(
        id=p.id,
        endpoint=p.endpoint,
        api_key_encrypted=enc,
        models=models_str,
        priority=p.priority,
        credit_threshold=p.credit_threshold,
        provider_type=p.provider_type if (p.provider_type and str(p.provider_type).strip()) else None,
        supports_tools=1 if p.supports_tools else 0,
        supports_streaming=1 if p.supports_streaming else 0,
        supports_multimodal=1 if p.supports_multimodal else 0,
    )
    db.provider_priority_set(p.id, p.priority)
    health = get_all_health()
    provider = {
        "id": p.id,
        "endpoint": p.endpoint,
        "provider_type": p.provider_type or "openai_compat",
        "models": models_str,
        "priority": p.priority,
        "credit_threshold": p.credit_threshold,
        "supports_tools": p.supports_tools,
        "supports_streaming": p.supports_streaming,
        "supports_multimodal": p.supports_multimodal,
        "healthy": health.get(p.id, True),
    }
    return {"ok": True, "provider": provider}


class ProviderPatch(BaseModel):
    endpoint: Optional[str] = None
    models: Optional[list[str] | str] = None
    priority: Optional[int] = None
    credit_threshold: Optional[float] = None
    provider_type: Optional[str] = None
    supports_tools: Optional[bool] = None
    supports_streaming: Optional[bool] = None
    supports_multimodal: Optional[bool] = None
    api_key: Optional[str] = None


@router.patch("/providers/{provider_id}")
async def update_provider(provider_id: str, p: ProviderPatch):
    """PATCH /admin/providers/{id} — update allowed fields; re-encrypt if api_key provided."""
    if not db.provider_get(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    kwargs: dict[str, Any] = {}
    if p.endpoint is not None:
        kwargs["endpoint"] = p.endpoint
    if p.models is not None:
        kwargs["models"] = p.models if isinstance(p.models, str) else json.dumps(p.models)
    if p.priority is not None:
        kwargs["priority"] = p.priority
    if p.credit_threshold is not None:
        kwargs["credit_threshold"] = p.credit_threshold
    if p.provider_type is not None:
        kwargs["provider_type"] = p.provider_type.strip() or None
    if p.supports_tools is not None:
        kwargs["supports_tools"] = 1 if p.supports_tools else 0
    if p.supports_streaming is not None:
        kwargs["supports_streaming"] = 1 if p.supports_streaming else 0
    if p.supports_multimodal is not None:
        kwargs["supports_multimodal"] = 1 if p.supports_multimodal else 0
    if p.api_key is not None:
        if p.api_key and not encryption_available():
            raise HTTPException(
                status_code=400,
                detail="ROUTER_ENCRYPTION_KEY is required to store provider API keys. Set it (min 16 characters) and retry.",
            )
        kwargs["api_key_encrypted"] = encrypt_api_key(p.api_key)
    if kwargs:
        db.provider_update(provider_id, **kwargs)
    if p.priority is not None:
        db.provider_priority_set(provider_id, p.priority)
    return {"id": provider_id, "updated": True}


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """DELETE /admin/providers/{id} — cascade: provider_priority, failover_conditions, agent_override where provider_id = id."""
    if not db.provider_get(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    db.provider_delete(provider_id)
    return {"deleted": provider_id}


@router.get("/credit")
async def get_credit():
    """GET /admin/credit — per-provider supported, enforceable, balance, currency, below_threshold, as_of, error. Never raw."""
    state = get_all_credit_state()
    return {
        "providers": [
            {"id": pid, **s}
            for pid, s in state.items()
        ]
    }


class OverrideBody(BaseModel):
    provider_id: Optional[str] = None


@router.post("/override")
async def post_override(request: Request, body: OverrideBody):
    """POST /admin/override — session_id from Bearer or X-Router-Session-Id; upsert agent_override."""
    session_id = get_session_id(request)
    db.agent_override_set(session_id, body.provider_id)
    current = db.agent_override_get(session_id)
    return {"ok": True, "current_provider": current}


class EstimateCostBody(BaseModel):
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@router.post("/estimate-cost")
async def estimate_cost(body: EstimateCostBody):
    """POST /admin/estimate-cost — MVP: placeholder. Contract: model optional; prompt_tokens and completion_tokens must be non-negative when provided."""
    if body.prompt_tokens is not None and body.prompt_tokens < 0:
        raise HTTPException(status_code=400, detail="prompt_tokens must be non-negative")
    if body.completion_tokens is not None and body.completion_tokens < 0:
        raise HTTPException(status_code=400, detail="completion_tokens must be non-negative")
    return {
        "estimated_cost": 0.0,
        "currency": "USD",
        "model": body.model or "",
        "tokens": (body.prompt_tokens or 0) + (body.completion_tokens or 0),
    }


def _normalize_failover_for_response(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map DB shape (condition_type, threshold_value) to PRD shape (condition, value)."""
    out = []
    for r in rows:
        c = r.get("condition_type", "")
        if c == "health_failure":
            c = "health"
        out.append({
            "id": r.get("id"),
            "provider_id": r.get("provider_id"),
            "condition": c,
            "value": r.get("threshold_value"),
            "updated_at": r.get("updated_at"),
        })
    return out


@router.get("/routing-config")
async def get_routing_config():
    """GET /admin/routing-config — strategy, provider_order, failover from DB. provider_order is the effective routing order used by the routing engine."""
    rc = db.routing_config_get()
    order = db.provider_priority_get_all()
    failover_rows = db.failover_conditions_get_all()
    return {
        "strategy": rc.get("strategy", "priority"),
        "provider_order": [pid for pid, _ in sorted(order, key=lambda x: x[1])] if order else [p["id"] for p in sorted(db.provider_list(), key=lambda x: x["priority"])],
        "failover": _normalize_failover_for_response(failover_rows),
    }


class FailoverItem(BaseModel):
    """One failover condition: PRD shape condition (credit_threshold|health), value optional."""
    provider_id: str
    condition: Literal["credit_threshold", "health"]
    value: Optional[float] = None


class RoutingConfigBody(BaseModel):
    strategy: Optional[str] = None
    cost_optimization: Optional[bool] = None
    provider_order: Optional[list[str]] = None
    failover: Optional[list[FailoverItem]] = None


@router.put("/routing-config")
@router.patch("/routing-config")
async def set_routing_config(body: RoutingConfigBody):
    """PUT/PATCH /admin/routing-config — partial update (per PRD): only provided fields are updated; unset fields left unchanged. Same semantics for both verbs."""
    if body.strategy is not None or body.cost_optimization is not None:
        db.routing_config_set(
            strategy=body.strategy,
            cost_optimization=1 if body.cost_optimization else (0 if body.cost_optimization is False else None),
        )
    if body.provider_order is not None:
        for i, pid in enumerate(body.provider_order):
            db.provider_priority_set(pid, i)
    if body.failover is not None:
        # PRD condition "health" -> DB condition_type "health_failure"
        conditions = []
        for item in body.failover:
            ctype = "health_failure" if item.condition == "health" else item.condition
            conditions.append((item.provider_id, ctype, item.value))
        db.failover_conditions_replace_all(conditions)
    config = await get_routing_config()
    return {"ok": True, "routing_config": config}
