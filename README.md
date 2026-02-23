# Sanctum Router

**OpenRouter’s role—but local, extensible, and wired into the agent stack.** A self-hosted, OpenAI-compatible inference proxy that routes agent LLM requests across multiple providers (Venice.ai, Featherless.ai, local backends, etc.) with credit-aware failover, capability gating, and full control via Config API and SMCP plugins.

- **Self-hosted:** You run it; you own data, control, and logs.
- **Agent/ops integrated:** SMCP plugins and CLI let agents and ops query or update routing, providers, and overrides at runtime.
- **Capability-aware:** Route by tools, streaming, and multimodal support—not just model string.
- **Single source of truth:** Provider definitions, routing state, and failover rules live in a local SQLite DB (credentials encrypted at rest).

## Docs

- **[Product Requirements Document (PRD)](docs/PRD.md)** — Positioning, full OAI/Config API spec, DB schema, MVP decisions.
- **[Phase 1 Implementation Plan](docs/plan.md)** — Ordered execution plan for the MVP.

## Quick start

1. **Clone and install**
   ```bash
   cd sanctum-router
   python3 -m venv .venv && .venv/bin/pip install -e .
   ```

2. **Set environment** (see [Env reference](#env-reference) below)
   ```bash
   export ROUTER_CLIENT_KEY=your-client-key
   export ROUTER_ADMIN_KEY=your-admin-key
   export ROUTER_ENCRYPTION_KEY=your-32-char-encryption-key
   export ROUTER_DB_PATH=/data/router.db   # or /tmp/router.db for dev
   ```

3. **Run**
   ```bash
   .venv/bin/uvicorn router.main:app --host 127.0.0.1 --port 8480
   ```
   Or with Docker: `docker compose up --build`. Port mapping is **127.0.0.1:8480:8480** (localhost-only on the host).

4. **Use**
   - Proxy (OpenAI-compatible): `http://127.0.0.1:8480/v1/models`, `/v1/chat/completions`, `/v1/embeddings` with `Authorization: Bearer <ROUTER_CLIENT_KEY>`.
   - Config API: `http://127.0.0.1:8480/admin/status`, `/admin/providers`, etc. with `Authorization: Bearer <ROUTER_ADMIN_KEY>`.
   - CLI: `router-cli status`, `router-cli providers list`, `router-cli credit`, etc. (requires `ROUTER_URL` and `ROUTER_ADMIN_KEY`).

## Env reference

| Variable | Description |
|----------|-------------|
| `ROUTER_CLIENT_KEY` | Bearer token for `/v1/*` (proxy API). Required in production. |
| `ROUTER_ADMIN_KEY` | Bearer or X-API-Key for `/admin/*` (Config API). |
| `ROUTER_ENCRYPTION_KEY` | Key for encrypting provider API keys in the DB (min 16 chars). |
| `ROUTER_DB_PATH` | SQLite path (default: `/data/router.db`). Mount a volume in Docker. |
| `ROUTER_CONFIG` | Optional path to YAML config file (bootstrap + server.port). |
| `ROUTER_PORT` | Override server port (default 8480). |
| `ROUTER_URL` | Base URL for CLI/plugins (e.g. `http://127.0.0.1:8480`). |

## Security warning

- **Bind to localhost by default.** Do not expose the router or Config API publicly. Use Docker port mapping `127.0.0.1:8480:8480` so only the host can reach it.
- **Config API and SMCP tools have write/admin access.** Loading SMCP plugins that call the Config API is an intentional security boundary—use only in **trusted/local** environments.

## Repo structure

```
sanctum-router/
├── README.md
├── LICENSE, LICENSE-DOCS
├── pyproject.toml, requirements.txt
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
    ├── PRD.md
    └── plan.md
```

## Licenses

- **Code:** [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).
- **Documentation and other non-code materials:** [Creative Commons Attribution-ShareAlike 4.0 International](LICENSE-DOCS) (CC-BY-SA 4.0). See [LICENSE-DOCS](LICENSE-DOCS) and the [CC-BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode).

## Contributing

Contributions are welcome. By contributing code, you agree to license it under AGPL-3.0. Documentation and non-code contributions are under CC-BY-SA 4.0.
