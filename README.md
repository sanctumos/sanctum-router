# Sanctum Router

**OpenRouter’s *role*—but local, extensible, and wired into the agent stack.** A self-hosted, OpenAI-compatible inference proxy that routes agent LLM requests across multiple providers with policy-enforced gating, credit-aware failover, and full control via Config API and SMCP plugins.

---

## What is Sanctum Router?

**Sanctum Router** is a local, self-hosted **OpenAI-compatible inference proxy**. It sits between agent frameworks (Letta/Sanctum) and multiple LLM backends (Venice, Featherless, local OpenAI-compatible servers, etc.) and provides a single stable API surface:

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`

The router chooses which backend to use **at request time**, based on deterministic policy (capabilities, credits, health), and can fail over automatically when a provider is unavailable.

---

## The “Entorhinal Cortex” concept (why this exists)

In the Sanctum stack, we model this component after the **entorhinal cortex**: a gateway between **self** and **cognition**.

- **Self** = memory/state, operational constraints, and tool-driven behavior (the agent system’s continuity).
- **Cognition** = the model providers that perform inference.

Just like the entorhinal cortex mediates traffic between hippocampal memory and neocortical cognition, Sanctum Router mediates traffic between the agent and the available model substrates—selectively and predictably.

This is why routing is not “random load balancing.” It’s **policy-enforced gating** between identity/continuity and compute.

---

## Design goals (Phase 1 / MVP)

### 1) Single drop-in OpenAI endpoint

Any OpenAI-speaking client should work by changing only:

- **Base URL** → router URL  
- **API key** → `ROUTER_CLIENT_KEY`

### 2) Deterministic routing (no “AI complexity” in MVP)

Phase 1 routing is explicit and rule-based:

- **Capability gating**
  - If the request includes `tools`, route only to providers with `supports_tools=true`
  - If the request is **multimodal** (images — detected via OpenAI-style message content items of type `image_url` / `input_image`), route only to providers with `supports_multimodal=true`
  - If `stream: true`, route only to providers with `supports_streaming=true`

- **Health failover**
  - Providers that time out or fail health checks are skipped

- **Credit threshold failover**
  - Providers below their configured credit threshold are skipped
  - Providers with “unknown credit” can be treated as available (no threshold enforcement)

### 3) Namespace-not-binding model IDs

The router uses canonical model IDs to avoid collisions:

- **Canonical:** `<provider>+<model>` (e.g. `venice+kimi-k2`)
- **Optional aliases** (e.g. `kimi-k2` → `venice+kimi-k2`)

**Important:** provider prefixes are **namespacing**, not hard binding. If a request for `venice+kimi-k2` must fail over, the router may serve the request from another provider that declares the same upstream model name (`kimi-k2`), while still echoing the requested model id in the response for client stability.

The actual backend used is reported via response headers:

- `X-Router-Provider: <provider_id>`
- `X-Router-Upstream-Model: <model_as_sent_to_backend>` (optional)

---

## Control plane (Config API) + tools

Sanctum Router exposes a **Config API** under `/admin/*` for operational control:

- Provider CRUD
- Routing config (order, failover conditions)
- Credit visibility
- Session override (pin a provider)

Operators interact with `/admin` via:

- **CLI** (thin HTTP client)
- **SMCP plugins** (tools that call the Config API)

### Security posture (intentional)

This system is designed for **trusted localhost deployments** (same machine as Letta). The Config API and SMCP write tools are intentionally powerful and are considered an **intentional security hole** if exposed publicly. Default posture is to bind to `127.0.0.1` and avoid public port exposure.

---

## Persistence and secrets

Sanctum Router uses a **SQLite DB in a persistent Docker volume** as the single source of truth for providers and routing config.

Provider API keys are stored **encrypted at rest** in SQLite using `ROUTER_ENCRYPTION_KEY` from the environment, and are only decrypted in memory when making upstream calls. No plaintext secrets are stored in DB or logs.

---

## Quick start

**Docker:** Set `ROUTER_CLIENT_KEY`, `ROUTER_ADMIN_KEY`, `ROUTER_ENCRYPTION_KEY`, then `docker compose up --build -d`. Router binds to localhost; map ports as `127.0.0.1:8480:8480`.

**Local:** `pip install -e .`, set the same env vars and `ROUTER_DB_PATH`, then `uvicorn router.main:app --host 127.0.0.1 --port 8480`.

**Full guide (curl, CLI, first provider):** [docs/QUICKSTART.md](docs/QUICKSTART.md).

---

## Documentation

Comprehensive docs live in **[docs/](docs/)**:

| Document | Description |
|----------|-------------|
| **[docs/README.md](docs/README.md)** | Documentation index and suggested reading order. |
| **[docs/QUICKSTART.md](docs/QUICKSTART.md)** | Get running: Docker, local install, curl and CLI examples. |
| **[docs/OVERVIEW.md](docs/OVERVIEW.md)** | What Sanctum Router is, Entorhinal Cortex concept, design goals. |
| **[docs/CONTROL_PLANE.md](docs/CONTROL_PLANE.md)** | Config API, CLI, SMCP plugins, security posture. |
| **[docs/PERSISTENCE_AND_SECRETS.md](docs/PERSISTENCE_AND_SECRETS.md)** | SQLite, encrypted keys, Docker volumes. |
| **[docs/REFERENCE.md](docs/REFERENCE.md)** | Env vars, session override, API summary, repo structure. |
| **[docs/PRD.md](docs/PRD.md)** | Product Requirements Document: full API spec, DB schema. |
| **[docs/plan.md](docs/plan.md)** | Phase 1 implementation plan. |

---

## Env reference

| Variable | Description |
|----------|-------------|
| `ROUTER_CLIENT_KEY` | Bearer token for `/v1/*` (proxy API). Required in production. |
| `ROUTER_ADMIN_KEY` | Bearer or X-API-Key for `/admin/*` (Config API). |
| `ROUTER_ENCRYPTION_KEY` | Symmetric key for encrypting provider API keys at rest (format depends on implementation; see [docs](docs/PERSISTENCE_AND_SECRETS.md)). |
| `ROUTER_DB_PATH` | SQLite path (default: `/data/router.db`). Mount a volume in Docker. |
| `ROUTER_CONFIG` | Optional path to YAML config file (bootstrap + server.port). |
| `ROUTER_PORT` | Override server port (default 8480). |
| `ROUTER_URL` | Base URL for CLI/plugins (e.g. `http://127.0.0.1:8480`). |

See [docs/REFERENCE.md](docs/REFERENCE.md) for session override, API summary, and repo structure.

---

## Session override

**Recommended (MVP):** set `ROUTER_ADMIN_KEY` = `ROUTER_CLIENT_KEY` unless you explicitly need them separated.

Provider override is keyed by **session ID**: either `X-Router-Session-Id` or the hash of the request’s Bearer token. The CLI uses the admin key, so overrides set via the CLI apply to the **admin** session. For proxy clients to see a CLI-set override, they must use the same session: send the same Bearer token (when client and admin keys match) or the same `X-Router-Session-Id` on proxy requests. When admin and client keys differ, proxy clients must send the same session identifier on `/v1/*` requests for CLI-set overrides to apply.

---

## Security warning

- **Bind to localhost by default.** Do not expose the router or Config API publicly. Use Docker port mapping `127.0.0.1:8480:8480` so only the host can reach it.
- **Config API and SMCP tools have write/admin access.** Loading SMCP plugins that call the Config API is an intentional security boundary—use only in **trusted/local** environments. See [docs/CONTROL_PLANE.md](docs/CONTROL_PLANE.md).

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
    ├── README.md           # Documentation index
    ├── QUICKSTART.md       # Full quickstart guide
    ├── OVERVIEW.md, CONTROL_PLANE.md, PERSISTENCE_AND_SECRETS.md, REFERENCE.md
    ├── PRD.md
    └── plan.md
```

---

## Licenses

- **Code:** [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).
- **Documentation and other non-code materials:** [Creative Commons Attribution-ShareAlike 4.0 International](LICENSE-DOCS) (CC-BY-SA 4.0). See [LICENSE-DOCS](LICENSE-DOCS) and the [CC-BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode).

---

## Contributing

Contributions are welcome. By contributing code, you agree to license it under AGPL-3.0. Documentation and non-code contributions are under CC-BY-SA 4.0.
