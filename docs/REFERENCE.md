# Reference — Env, session override, API summary

Quick reference for environment variables, session override behavior, and proxy vs admin API.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `ROUTER_CLIENT_KEY` | Bearer token for `/v1/*` (proxy API). Required in production. |
| `ROUTER_ADMIN_KEY` | Bearer or X-API-Key for `/admin/*` (Config API). |
| `ROUTER_ENCRYPTION_KEY` | Symmetric key for encrypting provider API keys at rest (format depends on implementation; see [PERSISTENCE_AND_SECRETS.md](PERSISTENCE_AND_SECRETS.md)). |
| `ROUTER_DB_PATH` | SQLite path (default: `/data/router.db`). Mount a volume in Docker. |
| `ROUTER_CONFIG` | Optional path to YAML config file (bootstrap + server.port). |
| `ROUTER_PORT` | Override server port (default 8480). |
| `ROUTER_URL` | Base URL for CLI/plugins (e.g. `http://127.0.0.1:8480`). |

---

## Session override

**Recommended (MVP):** set `ROUTER_ADMIN_KEY` = `ROUTER_CLIENT_KEY` unless you explicitly need them separated.

Provider override is keyed by **session ID**:

- Session ID = hash of the request’s **Bearer token**, unless the client sends **`X-Router-Session-Id`**, in which case that value is used.
- The **CLI** uses the admin key, so overrides set via the CLI apply to the **admin** session.
- For proxy clients to see a CLI-set override, they must use the **same session**: same Bearer token (when client and admin keys match) or the same `X-Router-Session-Id` on `/v1/*` requests.
- When admin and client keys differ, proxy clients must send the same session identifier on `/v1/*` requests for CLI-set overrides to apply.

---

## Proxy API (`/v1/*`) — summary

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/v1/models` | Bearer `ROUTER_CLIENT_KEY` | List models (from DB; router does not enumerate full upstream catalogs in MVP). |
| POST | `/v1/chat/completions` | Bearer `ROUTER_CLIENT_KEY` | Chat completion (streaming and non-streaming). |
| POST | `/v1/embeddings` | Bearer `ROUTER_CLIENT_KEY` | Create embeddings. |

Responses include `X-Router-Provider` (and optionally `X-Router-Upstream-Model`). Errors use OpenAI-style JSON body. Full semantics in [PRD.md](PRD.md).

---

## Config API (`/admin/*`) — summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/status` | Router status, health, current_provider, providers_healthy |
| GET | `/admin/providers` | List providers |
| POST | `/admin/providers` | Add provider |
| PATCH | `/admin/providers/{id}` | Update provider (partial) |
| DELETE | `/admin/providers/{id}` | Remove provider |
| GET | `/admin/credit` | Per-provider credit/balance |
| POST | `/admin/override` | Set/clear session override (pin provider) |
| POST | `/admin/estimate-cost` | Estimate cost for model + tokens |
| GET | `/admin/routing-config` | Get routing config |
| PUT / PATCH | `/admin/routing-config` | Set routing config |

Auth: `Authorization: Bearer <ROUTER_ADMIN_KEY>` or `X-API-Key: <ROUTER_ADMIN_KEY>`. Full request/response shapes in [PRD.md](PRD.md).

---

## Health

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | None | Docker/orchestration healthcheck. Returns `{"status":"ok"}` or `{"status":"degraded","db":"error"}`. |

---

## Repo structure

```
sanctum-router/
├── README.md
├── LICENSE, LICENSE-DOCS
├── pyproject.toml
├── Dockerfile, docker-compose.yaml
├── router/                 # Main application
│   ├── main.py             # FastAPI app, /v1/* and /admin/*
│   ├── config.py, db.py, auth.py
│   ├── proxy.py, admin.py
│   ├── routing_engine.py, credit_health.py
│   ├── adapters/
│   └── cli.py              # router-cli
├── plugins/
│   └── sanctum_router/     # SMCP plugin (copy to MCP_PLUGINS_DIR)
└── docs/
    ├── README.md           # This documentation index
    ├── QUICKSTART.md
    ├── OVERVIEW.md
    ├── CONTROL_PLANE.md
    ├── PERSISTENCE_AND_SECRETS.md
    ├── REFERENCE.md
    ├── PRD.md
    └── plan.md
```
