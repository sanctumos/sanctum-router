#!/usr/bin/env python3
"""
CLI: thin HTTP client for Config API. Plan 9.
ROUTER_URL + ROUTER_ADMIN_KEY for /admin/*. UCW-wrapable.
"""

import argparse
import json
import os
import sys

import httpx


def _base_url() -> str:
    url = os.environ.get("ROUTER_URL", "http://127.0.0.1:8480")
    return url.rstrip("/")


def _headers() -> dict[str, str]:
    key = os.environ.get("ROUTER_ADMIN_KEY", "")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _get(path: str) -> dict:
    r = httpx.get(_base_url() + path, headers=_headers(), timeout=30.0)
    r.raise_for_status()
    return r.json()


def _post(path: str, json_body: dict | None = None) -> dict:
    r = httpx.post(_base_url() + path, headers=_headers(), json=json_body or {}, timeout=30.0)
    r.raise_for_status()
    return r.json() if r.content else {}


def _patch(path: str, json_body: dict) -> dict:
    r = httpx.patch(_base_url() + path, headers=_headers(), json=json_body, timeout=30.0)
    r.raise_for_status()
    return r.json() if r.content else {}


def _put(path: str, json_body: dict) -> dict:
    r = httpx.put(_base_url() + path, headers=_headers(), json=json_body, timeout=30.0)
    r.raise_for_status()
    return r.json() if r.content else {}


def _delete(path: str) -> dict:
    r = httpx.delete(_base_url() + path, headers=_headers(), timeout=30.0)
    r.raise_for_status()
    return r.json() if r.content else {"deleted": path.split("/")[-1]}


def cmd_status(json_out: bool) -> None:
    data = _get("/admin/status")
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Status:", data.get("status", ""))
        print("Version:", data.get("version", ""))
        print("Uptime (s):", data.get("uptime_seconds", 0))
        print("Providers healthy:", data.get("providers_healthy", {}))


def cmd_providers_list(json_out: bool) -> None:
    data = _get("/admin/providers")
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        for p in data:
            print(p.get("id", ""), p.get("endpoint", ""), "healthy=", p.get("healthy", True))


def cmd_providers_add(args: argparse.Namespace, json_out: bool) -> None:
    body = {
        "id": args.id,
        "endpoint": args.endpoint,
        "models": args.models.split(",") if args.models else [],
        "priority": args.priority or 1,
        "credit_threshold": getattr(args, "credit_threshold", None),
        "supports_tools": getattr(args, "supports_tools", True),
        "supports_streaming": getattr(args, "supports_streaming", True),
        "supports_multimodal": getattr(args, "supports_multimodal", False),
        "api_key": getattr(args, "api_key", None),
    }
    data = _post("/admin/providers", body)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Created provider:", data.get("id", ""))


def cmd_providers_remove(provider_id: str, json_out: bool) -> None:
    data = _delete(f"/admin/providers/{provider_id}")
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Deleted:", data.get("deleted", provider_id))


def cmd_routing_get(json_out: bool) -> None:
    data = _get("/admin/routing-config")
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Strategy:", data.get("strategy", ""))
        print("Provider order:", data.get("provider_order", []))


def cmd_routing_set(args: argparse.Namespace, json_out: bool) -> None:
    body = {}
    if getattr(args, "strategy", None):
        body["strategy"] = args.strategy
    if getattr(args, "provider_order", None):
        body["provider_order"] = args.provider_order.split(",") if isinstance(args.provider_order, str) else args.provider_order
    if getattr(args, "cost_optimization", None) is not None:
        body["cost_optimization"] = args.cost_optimization
    if getattr(args, "failover", None):
        try:
            body["failover"] = json.loads(args.failover) if isinstance(args.failover, str) else args.failover
        except (json.JSONDecodeError, TypeError):
            body["failover"] = []
    data = _put("/admin/routing-config", body)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Updated routing config")


def cmd_override_set(provider_id: str | None, json_out: bool) -> None:
    body = {"provider_id": provider_id}
    data = _post("/admin/override", body)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Override:", data.get("current_provider", "cleared"))


def cmd_credit(json_out: bool) -> None:
    data = _get("/admin/credit")
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        for pid, info in data.items():
            print(pid, "balance=", info.get("balance"), "below_threshold=", info.get("below_threshold", False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sanctum Router CLI — Config API client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available commands:
  status      GET /admin/status
  providers   list | add | remove (--id, --endpoint, etc.)
  routing     get | set (--strategy, --provider-order, --failover)
  override    set (provider_id or omit to clear)
  credit      GET /admin/credit

Use --json for machine-readable output. UCW/SMCP: use --describe on the sanctum_router plugin for full tool spec.
        """,
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="GET /admin/status")

    p_providers = sub.add_parser("providers", help="Provider commands")
    p_providers.add_argument("sub", nargs="?", choices=["list", "add", "remove"], help="list | add | remove")
    p_providers.add_argument("--id", help="Provider id (add/remove)")
    p_providers.add_argument("--endpoint", help="Provider endpoint (add)")
    p_providers.add_argument("--models", help="Comma-separated models (add)")
    p_providers.add_argument("--priority", type=int, help="Priority (add)")
    p_providers.add_argument("--credit-threshold", type=float, dest="credit_threshold")
    p_providers.add_argument("--api-key", dest="api_key")
    p_providers.add_argument("--supports-tools", type=bool, dest="supports_tools", default=True)
    p_providers.add_argument("--supports-streaming", type=bool, dest="supports_streaming", default=True)
    p_providers.add_argument("--supports-multimodal", type=bool, dest="supports_multimodal", default=False)

    p_routing = sub.add_parser("routing", help="Routing config")
    p_routing.add_argument("sub", nargs="?", choices=["get", "set"], help="get | set")
    p_routing.add_argument("--strategy", help="Strategy (set)")
    p_routing.add_argument("--provider-order", dest="provider_order", help="Comma-separated provider ids (set)")
    p_routing.add_argument("--cost-optimization", type=bool, dest="cost_optimization")
    p_routing.add_argument("--failover", help="JSON array of failover conditions, e.g. [{\"provider_id\":\"venice\",\"condition\":\"credit_threshold\",\"value\":0.5}]")

    p_override = sub.add_parser("override", help="Session override")
    p_override.add_argument("sub", nargs="?", choices=["set"], help="set")
    p_override.add_argument("provider_id", nargs="?", help="Provider id or omit to clear")

    sub.add_parser("credit", help="GET /admin/credit")

    args = parser.parse_args()
    json_out = getattr(args, "json", False)

    try:
        if args.command == "status":
            cmd_status(json_out)
        elif args.command == "providers":
            if args.sub == "list":
                cmd_providers_list(json_out)
            elif args.sub == "add":
                if not args.id or not args.endpoint:
                    print("providers add requires --id and --endpoint", file=sys.stderr)
                    return 1
                cmd_providers_add(args, json_out)
            elif args.sub == "remove":
                if not args.id:
                    print("providers remove requires --id", file=sys.stderr)
                    return 1
                cmd_providers_remove(args.id, json_out)
            else:
                cmd_providers_list(json_out)
        elif args.command == "routing":
            if args.sub == "set":
                cmd_routing_set(args, json_out)
            else:
                cmd_routing_get(json_out)
        elif args.command == "override":
            pid = getattr(args, "provider_id", None)
            cmd_override_set(pid, json_out)
        elif args.command == "credit":
            cmd_credit(json_out)
        else:
            parser.print_help()
        return 0
    except httpx.HTTPStatusError as e:
        print(e.response.text, file=sys.stderr)
        return 1
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
