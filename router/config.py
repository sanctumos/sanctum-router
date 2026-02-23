"""
Config loading: YAML file (ROUTER_CONFIG) + ENV overrides.
Env contract: ROUTER_CLIENT_KEY, ROUTER_ADMIN_KEY, ROUTER_ENCRYPTION_KEY,
ROUTER_DB_PATH, ROUTER_CONFIG. PRD §6 Config API, §12 Persistence & secrets, §9 Sample Configuration.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml


def _substitute_env(value: Any) -> Any:
    """Replace ${VAR} and $VAR in strings with os.environ."""
    if isinstance(value, str):
        def repl(m: re.Match) -> str:
            key = m.group(1) or m.group(2)
            return os.environ.get(key, m.group(0))
        return re.sub(r"\$\{([^}]+)\}|\$(\w+)", repl, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


def load_config() -> dict[str, Any]:
    """
    Load config from YAML (if ROUTER_CONFIG set) and apply ENV overrides.
    Returns a dict with server, providers, routing, monitoring.
    """
    out: dict[str, Any] = {
        "server": {"port": 8480, "admin_bind_localhost_only": True},
        "providers": {},
        "routing": {"strategy": "priority", "cost_optimization": False},
        "monitoring": {
            "credit_check_interval": 300,
            "health_check_interval": 60,
            "health_check_timeout": 10.0,
        },
    }

    config_path = os.environ.get("ROUTER_CONFIG")
    if config_path and Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data = _substitute_env(data)
        if "server" in data:
            out["server"].update(data["server"])
        if "providers" in data:
            out["providers"] = data["providers"]
        if "routing" in data:
            out["routing"].update(data["routing"])
        if "monitoring" in data:
            out["monitoring"].update(data["monitoring"])

    # ENV overrides for server.port
    port_env = os.environ.get("ROUTER_PORT")
    if port_env is not None:
        try:
            out["server"]["port"] = int(port_env)
        except ValueError:
            pass

    return out


def get_server_params(config: dict[str, Any]) -> tuple[str, int]:
    """Return (host, port) for uvicorn. Used by main.py and __main__.py to avoid duplication."""
    port = config["server"]["port"]
    bind_localhost = config["server"].get("admin_bind_localhost_only", True)
    host = "127.0.0.1" if bind_localhost else "0.0.0.0"
    return host, port


def get_env_contract() -> dict[str, str]:
    """Document and return env vars used by the router (for docs)."""
    return {
        "ROUTER_CLIENT_KEY": "Bearer token for /v1/* (proxy API). Required in prod.",
        "ROUTER_ADMIN_KEY": "Bearer or X-API-Key for /admin/* (Config API).",
        "ROUTER_ENCRYPTION_KEY": "Key for encrypting provider API keys in DB.",
        "ROUTER_DB_PATH": "SQLite DB path (default: /data/router.db).",
        "ROUTER_CONFIG": "Optional path to YAML config file.",
        "ROUTER_PORT": "Override server.port (default 8480).",
    }
