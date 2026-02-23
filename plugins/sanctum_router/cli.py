"""
SMCP plugin: tools implemented by HTTP calls to router Config API.
Requires ROUTER_URL and ROUTER_ADMIN_KEY. If ROUTER_ADMIN_KEY != ROUTER_CLIENT_KEY,
send X-Router-Session-Id on override and inference requests for overrides to apply.
SECURITY: Loading SMCP tools with write/admin access is an intentional security boundary;
use only in trusted/local environments.
"""

import json
import os
import subprocess
import sys

# Tools call the router CLI (which calls Config API). UCW-wrapable CLI.
ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:8480")
ROUTER_ADMIN_KEY = os.environ.get("ROUTER_ADMIN_KEY", "")


def _run_cli(args: list[str]) -> str:
    env = os.environ.copy()
    env["ROUTER_URL"] = ROUTER_URL
    env["ROUTER_ADMIN_KEY"] = ROUTER_ADMIN_KEY
    result = subprocess.run(
        [sys.executable, "-m", "router.cli", "--json"] + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) or ".",
    )
    if result.returncode != 0:
        return json.dumps({"error": result.stderr or result.stdout or "CLI failed"})
    return result.stdout or "{}"


def get_router_status() -> str:
    """Get router status (version, uptime, providers_healthy)."""
    return _run_cli(["status"])


def list_providers() -> str:
    """List configured providers."""
    return _run_cli(["providers", "list"])


def get_credit_status() -> str:
    """Get per-provider credit balance and below_threshold."""
    return _run_cli(["credit"])


def select_provider(provider_id: str | None = None) -> str:
    """Set session override to provider_id; pass empty to clear. Requires X-Router-Session-Id when keys differ."""
    return _run_cli(["override", "set", provider_id] if provider_id else ["override", "set"])


def estimate_cost(model: str = "", prompt_tokens: int = 0, completion_tokens: int = 0) -> str:
    """Estimate cost for model and token counts (MVP placeholder)."""
    return json.dumps({"message": "Use POST /admin/estimate-cost with model and tokens"})


def get_routing_config() -> str:
    """Get routing strategy and provider order."""
    return _run_cli(["routing", "get"])


def set_routing_config(strategy: str | None = None, provider_order: str | None = None) -> str:
    """Update routing config (strategy, comma-separated provider_order)."""
    args = ["routing", "set"]
    if strategy:
        args.extend(["--strategy", strategy])
    if provider_order:
        args.extend(["--provider-order", provider_order])
    return _run_cli(args)


if __name__ == "__main__":
    # Allow direct invocation for SMCP server discovery
    print(json.dumps({
        "tools": [
            "get_router_status",
            "list_providers",
            "get_credit_status",
            "select_provider",
            "estimate_cost",
            "get_routing_config",
            "set_routing_config",
        ]
    }))
