"""
Routing engine: provider order, capability gating, override, failover, model ID resolution.
Plan 4.1–4.6. No request/usage logging to DB.

Failover: failover_conditions in DB are persisted for API consistency and future use (e.g. Phase 2).
This engine currently uses only in-memory health and providers.credit_threshold for failover.
"""

import json
from typing import Any

from router import db
from router.credit_health import is_below_credit_threshold, is_healthy, set_healthy


def _provider_order() -> list[dict[str, Any]]:
    """Ordered list of providers: provider_priority table if present, else providers.priority."""
    priority_rows = db.provider_priority_get_all()
    if priority_rows:
        order = [pid for pid, _ in sorted(priority_rows, key=lambda x: x[1])]
        providers = {p["id"]: p for p in db.provider_list()}
        return [providers[pid] for pid in order if pid in providers]
    providers = db.provider_list()
    return sorted(providers, key=lambda p: p["priority"])


def _is_multimodal_request(body: dict[str, Any]) -> bool:
    """MVP: multimodal iff any message content item has type image_url or input_image."""
    messages = body.get("messages") or []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") in ("image_url", "input_image"):
                    return True
        elif isinstance(content, dict) and content.get("type") in ("image_url", "input_image"):
            return True
    return False


def resolve_canonical_model(request_model: str) -> str:
    """Public API: resolve alias to canonical id; otherwise return as-is."""
    return db.model_aliases_resolve(request_model) or request_model


def upstream_model_part(canonical_id: str) -> str:
    """Public API: if canonical is provider+model return model part; else return canonical_id."""
    if "+" in canonical_id:
        return canonical_id.split("+", 1)[1]
    return canonical_id


def _providers_with_model(providers: list[dict[str, Any]], upstream_model: str) -> list[dict[str, Any]]:
    """Filter to providers that list this upstream model (in their models JSON array)."""
    out = []
    for p in providers:
        models_raw = p.get("models") or "[]"
        if isinstance(models_raw, str):
            try:
                models = json.loads(models_raw)
            except (json.JSONDecodeError, TypeError):
                models = []
        else:
            models = models_raw
        if upstream_model in models:
            out.append(p)
    return out


def filter_by_capability(
    providers: list[dict],
    *,
    has_tools: bool = False,
    stream: bool = False,
    multimodal: bool = False,
) -> list[dict]:
    """Filter to providers that support requested capabilities."""
    out = []
    for p in providers:
        if has_tools and not p.get("supports_tools", True):
            continue
        if stream and not p.get("supports_streaming", True):
            continue
        if multimodal and not p.get("supports_multimodal", False):
            continue
        out.append(p)
    return out


def filter_available(providers: list[dict]) -> list[dict]:
    """Exclude unhealthy and below-credit-threshold."""
    out = []
    for p in providers:
        pid = p.get("id")
        if not is_healthy(pid):
            continue
        if is_below_credit_threshold(pid):
            continue
        out.append(p)
    return out


def resolve_candidates(
    session_id: str,
    request_model: str,
    body: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None, str]:
    """
    Return (ordered_candidates, chosen_provider_id, canonical_model_id).
    chosen_provider_id may be None if no candidate; canonical_model_id is for response model echo.
    """
    canonical = resolve_canonical_model(request_model)
    upstream_model = upstream_model_part(canonical)

    ordered = _provider_order()
    with_model = _providers_with_model(ordered, upstream_model)
    if not with_model:
        return [], None, canonical

    has_tools = bool(body.get("tools"))
    stream = bool(body.get("stream"))
    multimodal = _is_multimodal_request(body)
    capable = filter_by_capability(with_model, has_tools=has_tools, stream=stream, multimodal=multimodal)
    available = filter_available(capable)

    # Override is honored only when the provider is in the available set.
    override_provider_id = db.agent_override_get(session_id)
    if override_provider_id:
        for p in available:
            if p.get("id") == override_provider_id:
                return available, override_provider_id, canonical
        # Override provider not in available list; fall through to normal order

    chosen = available[0]["id"] if available else None
    return available, chosen, canonical


def mark_provider_unhealthy(provider_id: str) -> None:
    """On timeout/5xx, mark unhealthy in memory (plan 4.4)."""
    set_healthy(provider_id, False)
