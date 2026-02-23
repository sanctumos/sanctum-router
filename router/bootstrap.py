"""
Optional bootstrap: on first run, if DB has no providers and config has providers, seed from YAML/ENV.
Encrypt API keys during seed. PRD § Database schema Notes.
"""

import json
import os
from typing import Any

from router.crypto_utils import encrypt_api_key
from router import db


def bootstrap_from_config(config: dict[str, Any]) -> bool:
    """
    If no providers in DB and config has providers, seed providers (and optionally routing_config, provider_priority).
    Returns True if bootstrap ran, False if skipped.
    """
    if db.provider_count() > 0:
        return False
    providers = config.get("providers") or {}
    if not providers:
        return False

    routing = config.get("routing") or {}
    strategy = routing.get("strategy", "priority")
    cost_optimization = 1 if routing.get("cost_optimization") else 0
    db.routing_config_set(strategy=strategy, cost_optimization=cost_optimization)

    for i, (pid, p) in enumerate(providers.items()):
        if not isinstance(p, dict):
            continue
        endpoint = p.get("endpoint", "")
        api_key = p.get("api_key")
        if isinstance(api_key, str) and api_key.startswith("${") and api_key.endswith("}"):
            key = api_key[2:-1].strip()
            api_key = os.environ.get(key, "")
        encrypted = encrypt_api_key(api_key) if api_key else None
        models = p.get("models", [])
        models_str = models if isinstance(models, str) else json.dumps(models)
        priority = int(p.get("priority", i + 1))
        credit_threshold = p.get("credit_threshold")
        if credit_threshold is not None:
            credit_threshold = float(credit_threshold)
        supports_tools = 1 if p.get("supports_tools", True) else 0
        supports_streaming = 1 if p.get("supports_streaming", True) else 0
        supports_multimodal = 1 if p.get("supports_multimodal", False) else 0
        db.provider_insert(
            id=pid,
            endpoint=endpoint,
            api_key_encrypted=encrypted,
            models=models_str,
            priority=priority,
            credit_threshold=credit_threshold,
            supports_tools=supports_tools,
            supports_streaming=supports_streaming,
            supports_multimodal=supports_multimodal,
        )
        db.provider_priority_set(pid, priority)
    return True
