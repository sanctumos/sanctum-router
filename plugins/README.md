# Sanctum Router SMCP Plugins

Plugins for [sanctumos/smcp](https://github.com/sanctumos/smcp). Copy `sanctum_router` into your `MCP_PLUGINS_DIR`.

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
