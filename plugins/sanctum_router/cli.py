#!/usr/bin/env python3
"""
Sanctum Router SMCP plugin — Config API tools for SMCP.

Requires ROUTER_URL and ROUTER_ADMIN_KEY. If ROUTER_ADMIN_KEY != ROUTER_CLIENT_KEY,
send X-Router-Session-Id on override and inference requests for overrides to apply.

SMCP contract: --describe returns plugin spec; subcommands = tool names (sanctum_router__<command>).
SECURITY: Loading SMCP tools with write/admin access is an intentional security boundary;
use only in trusted/local environments.
"""

import argparse
import json
import os
import subprocess
import sys

ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:8480")
ROUTER_ADMIN_KEY = os.environ.get("ROUTER_ADMIN_KEY", "")


def _run_cli(args: list[str]) -> str:
    env = os.environ.copy()
    env["ROUTER_URL"] = ROUTER_URL
    env["ROUTER_ADMIN_KEY"] = ROUTER_ADMIN_KEY
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) or "."
    result = subprocess.run(
        [sys.executable, "-m", "router.cli", "--json"] + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    if result.returncode != 0:
        return json.dumps({"error": result.stderr or result.stdout or "CLI failed"})
    return result.stdout or "{}"


# --- Tool implementations (return JSON string for stdout) ---

def get_router_status() -> str:
    return _run_cli(["status"])


def list_providers() -> str:
    return _run_cli(["providers", "list"])


def get_credit_status() -> str:
    return _run_cli(["credit"])


def select_provider(provider_id: str | None = None) -> str:
    return _run_cli(["override", "set", provider_id] if provider_id else ["override", "set"])


def estimate_cost(model: str = "", prompt_tokens: int = 0, completion_tokens: int = 0) -> str:
    """MVP placeholder; router CLI has no estimate-cost subcommand yet."""
    return json.dumps({
        "message": "Use POST /admin/estimate-cost with model and tokens",
        "model": model or "",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    })


def get_routing_config() -> str:
    return _run_cli(["routing", "get"])


def set_routing_config(
    strategy: str | None = None,
    provider_order: str | None = None,
    failover: str | list | None = None,
) -> str:
    args = ["routing", "set"]
    if strategy:
        args.extend(["--strategy", strategy])
    if provider_order:
        args.extend(["--provider-order", provider_order])
    if failover is not None:
        args.extend(["--failover", json.dumps(failover) if isinstance(failover, list) else failover])
    return _run_cli(args)


# --- SMCP --describe spec (required for discovery) ---

def _describe_spec() -> dict:
    return {
        "plugin": {
            "name": "sanctum_router",
            "version": "1.0.0",
            "description": "Router status, providers, credit, override, routing config, estimate-cost. Calls router Config API.",
        },
        "commands": [
            {
                "name": "get_router_status",
                "description": "Get router status (version, uptime, providers_healthy).",
                "parameters": [],
            },
            {
                "name": "list_providers",
                "description": "List configured providers.",
                "parameters": [],
            },
            {
                "name": "get_credit_status",
                "description": "Get per-provider credit balance and below_threshold.",
                "parameters": [],
            },
            {
                "name": "select_provider",
                "description": "Set session override to provider_id; pass empty to clear. Requires X-Router-Session-Id when keys differ.",
                "parameters": [
                    {"name": "provider_id", "type": "string", "description": "Provider id or omit to clear", "required": False, "default": None},
                ],
            },
            {
                "name": "estimate_cost",
                "description": "Estimate cost for model and token counts (MVP placeholder).",
                "parameters": [
                    {"name": "model", "type": "string", "description": "Model id", "required": False, "default": ""},
                    {"name": "prompt_tokens", "type": "integer", "description": "Prompt token count", "required": False, "default": 0},
                    {"name": "completion_tokens", "type": "integer", "description": "Completion token count", "required": False, "default": 0},
                ],
            },
            {
                "name": "get_routing_config",
                "description": "Get routing strategy and provider order.",
                "parameters": [],
            },
            {
                "name": "set_routing_config",
                "description": "Update routing config (strategy, comma-separated provider_order, optional failover JSON array).",
                "parameters": [
                    {"name": "strategy", "type": "string", "description": "Strategy (e.g. priority)", "required": False, "default": None},
                    {"name": "provider_order", "type": "string", "description": "Comma-separated provider ids", "required": False, "default": None},
                    {"name": "failover", "type": "array", "description": "Failover conditions JSON array", "required": False, "default": None},
                ],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sanctum Router SMCP plugin — Config API tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available commands:
  get_router_status   Get router status (version, uptime, providers_healthy)
  list_providers      List configured providers
  get_credit_status   Get per-provider credit balance and below_threshold
  select_provider     Set session override to provider_id or clear
  estimate_cost       Estimate cost for model and token counts (placeholder)
  get_routing_config  Get routing strategy and provider order
  set_routing_config  Update routing config (strategy, provider_order, failover)

Examples:
  python cli.py --describe
  python cli.py get_router_status
  python cli.py select_provider --provider-id venice
  python cli.py set_routing_config --strategy priority --provider-order venice,featherless
        """,
    )
    parser.add_argument("--describe", action="store_true", help="Output plugin spec JSON for SMCP discovery")
    sub = parser.add_subparsers(dest="command", help="Tool command")

    sub.add_parser("get_router_status", help="Get router status")
    sub.add_parser("list_providers", help="List providers")
    sub.add_parser("get_credit_status", help="Get credit status")

    p_sel = sub.add_parser("select_provider", help="Set or clear session override")
    p_sel.add_argument("--provider-id", dest="provider_id", default=None, help="Provider id or omit to clear")

    p_est = sub.add_parser("estimate_cost", help="Estimate cost (placeholder)")
    p_est.add_argument("--model", default="", help="Model id")
    p_est.add_argument("--prompt-tokens", dest="prompt_tokens", type=int, default=0, help="Prompt tokens")
    p_est.add_argument("--completion-tokens", dest="completion_tokens", type=int, default=0, help="Completion tokens")

    sub.add_parser("get_routing_config", help="Get routing config")

    p_set = sub.add_parser("set_routing_config", help="Set routing config")
    p_set.add_argument("--strategy", default=None, help="Strategy")
    p_set.add_argument("--provider-order", dest="provider_order", default=None, help="Comma-separated provider ids")
    p_set.add_argument("--failover", dest="failover", action="append", default=None, help="Failover condition (repeat for multiple); each a JSON object")

    args = parser.parse_args()

    if args.describe:
        print(json.dumps(_describe_spec(), indent=2))
        return 0

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch: run tool and print JSON to stdout (SMCP captures this)
    result: str
    if args.command == "get_router_status":
        result = get_router_status()
    elif args.command == "list_providers":
        result = list_providers()
    elif args.command == "get_credit_status":
        result = get_credit_status()
    elif args.command == "select_provider":
        result = select_provider(provider_id=getattr(args, "provider_id", None))
    elif args.command == "estimate_cost":
        result = estimate_cost(
            model=getattr(args, "model", "") or "",
            prompt_tokens=getattr(args, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(args, "completion_tokens", 0) or 0,
        )
    elif args.command == "get_routing_config":
        result = get_routing_config()
    elif args.command == "set_routing_config":
        failover = getattr(args, "failover", None)
        if isinstance(failover, list):
            parsed = []
            for item in failover:
                if isinstance(item, str) and item:
                    try:
                        parsed.append(json.loads(item))
                    except json.JSONDecodeError:
                        pass
            failover = parsed if parsed else None
        elif isinstance(failover, str) and failover:
            try:
                failover = json.loads(failover)
            except json.JSONDecodeError:
                failover = None
        result = set_routing_config(
            strategy=getattr(args, "strategy", None),
            provider_order=getattr(args, "provider_order", None),
            failover=failover,
        )
    else:
        parser.print_help()
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
