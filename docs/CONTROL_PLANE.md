# Control plane — Config API, CLI, SMCP

Sanctum Router exposes a **Config API** under `/admin/*` for operational control. Operators interact with it via the **CLI** (thin HTTP client) or **SMCP plugins** (tools that call the Config API).

---

## Config API (`/admin/*`)

All admin endpoints require **ROUTER_ADMIN_KEY**: `Authorization: Bearer <ROUTER_ADMIN_KEY>` or `X-API-Key: <ROUTER_ADMIN_KEY>`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/status` | Router status, health, current provider, provider health map |
| GET | `/admin/providers` | List providers and capabilities |
| POST | `/admin/providers` | Add provider (id, endpoint, api_key?, models, priority, capabilities, credit_threshold?) |
| PATCH | `/admin/providers/{id}` | Update provider (partial) |
| DELETE | `/admin/providers/{id}` | Remove provider |
| GET | `/admin/credit` | Per-provider credit/balance and below-threshold |
| POST | `/admin/override` | Session override: pin provider (or clear with `provider_id: null`) |
| POST | `/admin/estimate-cost` | Estimate cost for model + prompt/completion tokens |
| GET | `/admin/routing-config` | Get routing config (provider_order, failover) |
| PUT / PATCH | `/admin/routing-config` | Set routing config (full or partial) |

All mutations persist to the router’s SQLite DB. See [PRD.md](PRD.md) for full request/response shapes.

---

## CLI

The CLI is a thin HTTP client. It needs:

- **ROUTER_URL** — e.g. `http://127.0.0.1:8480`
- **ROUTER_ADMIN_KEY** — for `/admin/*` auth

Commands map to Config API endpoints: `status`, `providers list/add/remove`, `routing get/set`, `override`, `credit`. Use `--json` for machine-readable output. The CLI is designed to be **UCW-wrapable** so the same capabilities can be exposed as SMCP tools.

---

## SMCP plugins

Router ships **SMCP plugins** (sanctumos/smcp–compatible) that implement tools by calling the Config API. You run your own SMCP server and load these plugins (e.g. into `MCP_PLUGINS_DIR`). No MCP server is bundled in the router image.

Typical tools (names may vary): `get_router_status`, `list_providers`, `get_credit_status`, `select_provider`, `estimate_cost`, `get_routing_config`, `set_routing_config`. Each tool calls the router’s Config API; state is persisted in SQLite inside the router.

Plugins require **ROUTER_URL** and **ROUTER_ADMIN_KEY** in the environment where the SMCP server runs.

---

## Security posture (intentional)

This system is designed for **trusted localhost deployments** (same machine as Letta).

- The Config API and SMCP write tools are **intentionally powerful** (provider CRUD, routing, override). They are considered an **intentional security hole** if exposed publicly.
- **Default posture:** bind to `127.0.0.1` and avoid public port exposure. Use Docker port mapping `127.0.0.1:8480:8480` so only the host can reach the router.
- Use Config API and SMCP plugins only in **trusted/local** environments.

See [REFERENCE.md](REFERENCE.md) for session override and env vars.
