# Sanctum Router SMCP Plugins

Plugins for [sanctumos/smcp](https://github.com/sanctumos/smcp). Copy `sanctum_router` into your `MCP_PLUGINS_DIR`.

## SMCP contract

The plugin follows the SMCP plugin design:

- **Discovery:** SMCP runs `python cli.py --describe` and expects JSON: `{ "plugin": { name, version, description }, "commands": [ { name, description, parameters } ] }`. Each command becomes a tool `sanctum_router__<name>`.
- **Execution:** SMCP runs `python cli.py <command> --arg1 val1 ...`. Arguments use `--kebab-case` (e.g. `--provider-id`). The plugin prints the tool result as JSON to stdout.
- **Fallback:** If `--describe` is not supported, SMCP parses `--help` for an "Available commands:" section; the plugin epilog includes that.

## Security warning

**Loading SMCP tools with write/admin access is an intentional security boundary.** These tools call the router Config API (add/remove providers, override, routing config). Use only in **trusted/local environments**. Do not expose the Config API or plugin controls to untrusted users.

## Session correlation (override)

If `ROUTER_ADMIN_KEY` and `ROUTER_CLIENT_KEY` differ, the inference client (Letta, etc.) **must** send the same `X-Router-Session-Id` header on `/v1/*` requests that the plugin uses on override calls, or overrides will not apply to that client's requests.

## Tools

- `get_router_status` — status, version, providers_healthy
- `list_providers` — configured providers
- `get_credit_status` — per-provider balance and below_threshold
- `select_provider` — set session override (or clear)
- `estimate_cost` — placeholder
- `get_routing_config` / `set_routing_config` — strategy and provider order

Requires `ROUTER_URL` and `ROUTER_ADMIN_KEY` in the environment.
