# Sanctum Router — Product Requirements Document (PRD)

---

## Positioning: OpenRouter, but local, extensible, and stack-deep

What we’re building is better understood as:

**“OpenRouter’s role—unified model routing—but local, extensible, and so deeply wired into the agent stack and ops tooling that it’s not just a gateway; it’s an operational substrate for sovereign AI development and experimental agent autonomy.”**

### How Sanctum Router is *closer to the stack* than OpenRouter

- **Self-hosted:** You run it; you own data, control, and every log path; you choose what agents, devs, and API keys interact with the router.
- **Pluggable into agent frameworks:** Native SMCP plugin structure means agents can directly invoke router controls, overrides, and config at runtime—no SaaS router offers this.
- **Near-real-time feedback loop:** Agents and ops can *query or update* router state and rules on the fly (e.g. credits, provider priority, session override) within limits you define.
- **Config/API and DB as first-class ops objects:** Routing, failover, and provider definitions are live objects, not just up-front config or SaaS dashboard toggles.
- **Capability-aware at routing time:** Not only “route by model string” but runtime policy—can this request use tools? streaming? multimodal? Failover and gating are explicit and programmable.
- **Local-first security/ops posture:** Run airgapped, integrate with on-prem services, add custom monitoring/alerting; avoid SaaS attack surface, vendor egress risk, and API drift.
- **Tweakable by agents:** With the control plane local, you can experiment with agentic self-management, feedback, and quota awareness at the router layer.
- **Ops hooks and dev UX:** Agents, ops, and scripts talk to the same router with deterministic behavior; no SaaS aggregator can match this OS-level integration.

### In short

**Sanctum Router = OpenRouter’s role, but local, extensible, and flexible at every integration surface.** It isn’t “another aggregator”; it’s closer to the root of your AI stack than any SaaS aggregator can be.

| **OpenRouter** | **Sanctum Router** |
|----------------|--------------------|
| Unified model marketplace API | Programmable, agent/ops-integrated, local AI routing subsystem—under your full control |

We’re not reinventing the idea—we’re **localizing**, **operationalizing**, and **empowering** it for builder/ops/sovereignty-first needs. That’s evolution, not duplication.

---

## 1. Executive Summary

**Sanctum Router** is a self-hosted, OpenAI-compatible inference proxy that routes agent LLM requests across multiple inference providers (e.g. Venice.ai, Featherless.ai, and generic OpenAI-compatible backends such as local, OpenRouter, Courier) based on capability, cost, and availability. Designed for agent frameworks like Letta and Sanctum, it enables credit-aware, intelligent routing and seamless multi-provider redundancy—all with a single drop-in interface.

**Delivery:** Self-hosted Docker container  
**Audience:** AI developers, self-hosting infra architects, agent framework builders

---

## 2. Problem Statement

- **Credit Exhaustion:** Single-provider systems fail when credits run out, requiring manual reconfiguration.
- **Cognitive Degradation:** Backup providers using weak models break agent identity/continuity.
- **Integration Fragmentation:** Each provider needs custom API handling; switching is tedious.
- **Automation Gap:** Agents cannot autonomously adapt to credit/capability changes.

---

## 3. Goals & Objectives

**Primary:**  
- Prevent downtime when credits exhaust; maintain agent cognitive capability across providers.

**Secondary:**  
- Expose unified OpenAI-compatible API.
- Enable agent-level credit/capability awareness (SMCP plugins).
- Deliver low-latency multi-provider routing.
- Easy deployment (<15min Docker startup).

**Success Metrics:**  
- Zero unscheduled downtime on credit exhaustion.
- Routing decisions match configured rules and capability gating >99% (no misroutes) in Phase 1; task/cost optimality metrics (e.g. >95%) in Phase 2.
- Agent usability/identity preserved regardless of routed provider.
- Setup-to-use under 15min.

---

## 4. Target Audience

**Primary:**  
- Devs running agent frameworks in prod/self-hosted.  
- Infra architects building AI redundancy strategies.

**Personas:**  
- Ops Dev: wants reliability, monitoring, low ops.
- Self-Hosting Hobbyist: wants plug & play, no surprises.
- Infra Architect: wants extensibility, analytics, proper control plane.

---

## 5. Product Overview

Sanctum Router is a Dockerized proxy providing an OpenAI-compatible API for agent requests. It routes each request to the optimal available provider based on rules, credit, and capability—failing over cleanly without human intervention.

### Key Features

- **Full OpenAI API compatibility (HTTP):** `/v1/chat/completions`, `/v1/embeddings`, **`/v1/models`** — request/response and **model listing** match OpenAI semantics; this is the proxy API, distinct from CLI controls
- **Multi-provider routing:** Venice.ai, Featherless.ai, and generic OpenAI-compatible backends (e.g. local, OpenRouter, Courier)
- **Credit & quota monitoring:** Periodic / near-real-time (e.g. configurable interval), with automatic failover
- **Intelligent routing logic:** By task complexity, cost, provider health, and rules
- **Agent control via SMCP:** Router ships **SMCP plugins** (sanctumos/smcp–compatible) for status, override, and routing logic; CLI is wrapped with **UCW** (actuallyrizzn/ucw) so the same surface is exposed as SMCP plugins — no bundled MCP server in the image
- **CLI utilities** for provider/config and routing logic (priority, failover rules); CLI designed to be UCW-wrapable for SMCP plugin generation
- **Observability:** health endpoint, config/status via Config API; no request/usage logging to DB in MVP
- **Local SQLite DB** for routing state and failover conditions

---

## 6. Functional Requirements

**Provider Management:**
- **Provider definitions live in the DB** (single source of truth). Add/remove/update providers via Config API (and optionally initial seed from YAML/ENV). No DB sprawl; YAML does not make config more secure.
- Credentials stored in DB **encrypted at rest** (key from environment); **no plaintext secrets** in DB or logs.
- CLI/Config API: provider add/list/remove/update; routing logic (provider order, failover conditions).
- Provider health checks; auto-mark unavailable. **Per-provider capability flags:** `supports_tools`, `supports_streaming` (and similar). If a request includes `tools`, the router **must** route only to providers with `supports_tools=true`.

**Routing Logic:**
- Priority/chain-based and rule-based routing
- **Configurable via Config API (CLI/SMCP):** provider order, failover conditions; state in SQLite.
- **Capability gating:** Requests with `tools` route only to providers with `supports_tools=true`; capability flags in DB.
- Task complexity estimation and cost optimization (post-MVP where not already specified).
- **Model IDs:** Canonical `<provider>+<model>`; optional alias map.

**Credit Awareness:**
- Quota balance monitoring for each provider
- Auto-switch provider at low-credit threshold
- Budget alarms and status reporting

**CLI/SMCP run outside the container — communication:**
- CLI and SMCP plugins run on the **host** (or in a different container). They have no filesystem or DB access to the router container. They communicate with the router **only over HTTP** to the router’s exposed port(s).
- The router **must expose a Config API** at `/admin` so that CLI and SMCP plugins can read/write routing config, providers (add/remove/update), credit status, and overrides. Auth: **ROUTER_ADMIN_KEY** (see § Config API).
- **CLI** = thin HTTP client calling the Config API. User sets `ROUTER_URL` and **ROUTER_ADMIN_KEY** (for `/admin/*`). Proxy clients use **ROUTER_CLIENT_KEY** for `/v1/*`.
- **SMCP plugins** = same: they need `ROUTER_URL` and **ROUTER_ADMIN_KEY** for Config API calls.

**Agent Integration (SMCP plugins — no bundled MCP server):**
- **SMCP** (sanctumos/smcp): plugin-based MCP server for the Sanctum/Animus/Letta ecosystem. Router **ships SMCP plugins** only; users run their own SMCP server and load these plugins (e.g. into `MCP_PLUGINS_DIR`). In **development**, an SMCP server is used for testing.
- **UCW** (actuallyrizzn/ucw): Universal Command Wrapper — generates MCP/SMCP-compatible plugin files from CLI commands. Router CLI is designed to be wrapped by UCW so the same capabilities are exposed as tools when the generated (or hand-written) plugin is loaded into SMCP.
- Plugin tools (exposed when plugins are loaded): `get_router_status()`, `list_providers()`, `get_credit_status()`, `select_provider(<provider>)`, `estimate_cost(<model>, <tokens>)`, `get_routing_config()`, `set_routing_config(...)` (or equivalent). Each tool **calls the router’s Config API**; state is persisted in SQLite inside the container.

**Config API (how CLI/SMCP outside the container talk to the router):**
- Router exposes **Config API** under **`/admin`** on the same port as the proxy. Auth: **`ROUTER_ADMIN_KEY`** (Bearer or X-API-Key); see § Config API (enumeration).
- Endpoints support: get/set routing config, list/add/remove/update providers, credit status, agent override (select_provider), estimate_cost. All mutations persist to SQLite.
- CLI and plugins require **`ROUTER_URL`** + **`ROUTER_ADMIN_KEY`** for `/admin/*` (and **`ROUTER_URL`** + **`ROUTER_CLIENT_KEY`** for `/v1/*` when calling the proxy).

**API Compatibility (OpenAI — distinct from CLI):**
- **Full OpenAI-compatible HTTP API:** clients use the router as a drop-in OpenAI endpoint. See **§ Full OpenAI API compatibility (reference)** below for the exact endpoint and response semantics.
- Model listing is part of the HTTP API only; provider/config and routing are managed via CLI or SMCP tools (which call the Config API), not via the models API

---

### Full OpenAI API compatibility (reference)

**Scope:** The router’s **Proxy API** must be a drop-in replacement for the OpenAI API for the endpoints listed. Clients that speak OpenAI (e.g. SDKs, Letta) should work without code changes beyond base URL and API key.

**Base path:** All proxy endpoints live under `/v1` (e.g. `https://router-host/v1/models`).

**Authentication:** Same as OpenAI: `Authorization: Bearer <API_KEY>`. The router may use its own API key for client auth; it then uses per-provider keys when forwarding to backends.

**Endpoints (must support):**

| Method | Path | Purpose | Request / Response |
|--------|------|---------|--------------------|
| **GET** | `/v1/models` | List available models | **Request:** No body. **Response:** `{ "object": "list", "data": [ { "id": "<model_id>", "object": "model", "created": <unix_ts>, "owned_by": "<provider>" }, ... ] }`. Router returns only models **enabled/declared in the DB** (plus aliases); it does **not** enumerate full upstream catalogs in MVP. `id` is the model identifier clients use in chat/embeddings. |
| **POST** | `/v1/chat/completions` | Chat completion | **Request:** JSON body with `model`, `messages`, and optional `temperature`, `max_tokens` / `max_completion_tokens`, `stream`, `tools`, `tool_choice`, etc., per [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create). **Capability gating:** If request includes `tools`, router **must** route only to providers with **`supports_tools=true`**. If request is **multimodal** (e.g. includes image content per OpenAI semantics), router **must** route only to providers with **`supports_multimodal=true`**. **Response (non-streaming):** `{ "id", "object": "chat.completion", "created", "model", "choices": [ ... ], "usage": { ... } }`. **Streaming:** SSE as per OpenAI. Router adds `X-Router-Provider` (and optionally `X-Router-Upstream-Model`) to indicate which provider served the request. |
| **POST** | `/v1/embeddings` | Create embeddings | **Request:** JSON body with `model`, `input` (string or array of strings), optional `encoding_format` ("float" | "base64"), `dimensions`, `user`. **Response:** `{ "object": "list", "data": [ { "object": "embedding", "embedding": [ <floats> ], "index": 0 } ], "model": "<model_id>", "usage": { "prompt_tokens", "total_tokens" } }`. |

**Streaming:** For `POST /v1/chat/completions`, when `stream: true`, the response must use Server-Sent Events (SSE) with the same event/chunk shape as OpenAI (e.g. `data: {"id","object":"chat.completion.chunk","choices":[...]}`). Optional final chunk may include `usage` when `stream_options.include_usage` is set.

**Errors:** Responses must use the same HTTP status codes and a JSON error body compatible with OpenAI so that clients can parse them. Standard shape: `{ "error": { "message": "<human-readable>", "type": "<error_type>", "code": "<error_code>" } }`. Map router/backend failures to appropriate status (e.g. 429 for rate limit, 503 for overload, 502 for upstream error). Include `x-request-id` in response headers when possible for debugging.

**Optional headers (recommended):** Echo or set `openai-version` and `openai-processing-ms` where applicable so clients that rely on them do not break.

---

### Config API (enumeration)

Base path: **`/admin`**. All admin endpoints require **ROUTER_ADMIN_KEY**: `Authorization: Bearer <ROUTER_ADMIN_KEY>` or `X-API-Key: <ROUTER_ADMIN_KEY>`. Proxy `/v1/*` uses **ROUTER_CLIENT_KEY** only. Ideally `/admin` is bindable to localhost-only.

**Key default (MVP):** `ROUTER_ADMIN_KEY` may be set equal to `ROUTER_CLIENT_KEY` for simplicity in trusted localhost deployments. If keys are different, callers **must** supply **`X-Router-Session-Id`** on both `/admin/override` and `/v1/*` requests so overrides apply to the intended inference session.

**Session correlation for overrides:**  
`session_id` is derived from the **hash of the request’s `Authorization` Bearer token** (same key ⇒ same session; Letta works with no extra headers when keys are the same). If the client sends **`X-Router-Session-Id`**, use that instead of the token hash. This ties `select_provider()` to the same session as subsequent inference calls.

| Method | Path | Purpose | Request / Response (summary) |
|--------|------|---------|-----------------------------|
| **GET** | `/admin/status` | Router status and health | **Response:** `{ "status": "ok"|"degraded", "version", "current_provider"?, "providers_healthy": { "<id>": true|false }, "uptime_seconds"?, ... }`. Used by CLI/SMCP `get_router_status()`. |
| **GET** | `/admin/providers` | List providers and capabilities | **Response:** `{ "providers": [ { "id", "endpoint", "models": [...], "priority", "healthy", "supports_tools", "supports_streaming", "supports_multimodal", "credit_threshold"?, ... } ] }`. Used by `list_providers()`. |
| **POST** | `/admin/providers` | Add provider | **Request:** `{ "id", "endpoint", "api_key"?, "models": [...], "priority", "credit_threshold"?, "supports_tools", "supports_streaming", "supports_multimodal", ... }`. Credentials stored encrypted in DB. **Response:** `{ "ok": true, "provider": { ... } }`. |
| **DELETE** | `/admin/providers/{id}` | Remove provider | **Response:** `{ "ok": true }`. |
| **PATCH** | `/admin/providers/{id}` | Update provider (endpoint, models, priority, capabilities, etc.) | **Request:** Partial provider object (e.g. `supports_tools`, `supports_streaming`, `supports_multimodal`). **Response:** `{ "ok": true, "provider": { ... } }`. |
| **GET** | `/admin/credit` | Per-provider credit/balance | **Response:** `{ "providers": [ { "id", "balance"?, "currency"?, "below_threshold": bool } ] }`. Used by `get_credit_status()`. |
| **POST** | `/admin/override` | Agent/session override: pin provider | **Request:** `{ "provider_id": "<id>" }` or `{ "provider_id": null }` to clear. **Response:** `{ "ok": true, "current_provider": "<id>" }`. Persisted in DB (e.g. by session/client id). Used by `select_provider()`. |
| **POST** | `/admin/estimate-cost` | Estimate cost for model + tokens | **Request:** `{ "model": "<id>", "prompt_tokens": n, "completion_tokens": n? }`. **Response:** `{ "estimated_cost"?, "currency"?, "model", "tokens" }`. Used by `estimate_cost()`. |
| **GET** | `/admin/routing-config` | Get routing config (priority, failover) | **Response:** `{ "strategy": "priority"|"rule", "provider_order": [ "<id>", ... ], "failover": [ { "provider_id", "condition": "credit_threshold"|"health", "value"?: ... } ], ... }`. Used by `get_routing_config()`. |
| **PUT** or **PATCH** | `/admin/routing-config` | Set routing config | **Request:** Same shape as GET response (partial for PATCH). **Response:** `{ "ok": true, "routing_config": { ... } }`. Persisted to SQLite. Used by `set_routing_config()`. |

All mutations (override, routing-config, provider add/remove/update) persist to the router’s SQLite DB. Provider definitions and encrypted credentials live in DB. CLI and SMCP plugins call these endpoints only.

---

### Database schema (SQLite)

Single SQLite database inside the container: provider definitions (with encrypted credentials), routing state, failover conditions, overrides. **No request/usage logging to DB in MVP.** No plaintext secrets in DB; credentials in `providers` are encrypted at rest (key from environment).

**Tables:**

```sql
-- Provider definitions (single source of truth). Credentials encrypted at rest.
CREATE TABLE providers (
  id TEXT PRIMARY KEY,              -- e.g. 'venice', 'featherless'
  endpoint TEXT NOT NULL,
  api_key_encrypted BLOB,            -- encrypted with key from env; NULL if no key
  models TEXT NOT NULL,             -- JSON array of enabled model names (upstream IDs)
  priority INTEGER NOT NULL,
  credit_threshold REAL,
  supports_tools INTEGER NOT NULL DEFAULT 1,
  supports_streaming INTEGER NOT NULL DEFAULT 1,
  supports_multimodal INTEGER NOT NULL DEFAULT 0,
  healthy INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Global routing settings (singleton)
CREATE TABLE routing_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  strategy TEXT NOT NULL DEFAULT 'priority',
  cost_optimization INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Explicit provider order override (optional; if empty, use providers.priority)
CREATE TABLE provider_priority (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL UNIQUE REFERENCES providers(id),
  priority_order INTEGER NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Failover conditions per provider
CREATE TABLE failover_conditions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL REFERENCES providers(id),
  condition_type TEXT NOT NULL,  -- 'credit_threshold' | 'health_failure'
  threshold_value REAL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Model alias: short name -> canonical provider+model (optional)
CREATE TABLE model_aliases (
  alias TEXT PRIMARY KEY,           -- e.g. 'kimi-k2'
  canonical_id TEXT NOT NULL        -- e.g. 'venice+kimi-k2'
);

-- Session-scoped provider override. session_id = hash(Authorization Bearer) or X-Router-Session-Id
CREATE TABLE agent_override (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL UNIQUE,
  provider_id TEXT REFERENCES providers(id),  -- NULL = clear override
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

```

**Notes:**
- **Providers:** Add/remove/update via Config API; optional bootstrap from YAML/ENV at first run. Credentials encrypted before write; decrypted only in memory when calling upstream.
- **Session:** `agent_override.session_id` = hash of the request’s Bearer token unless `X-Router-Session-Id` is set. When `ROUTER_ADMIN_KEY` equals `ROUTER_CLIENT_KEY`, the same token ties override to inference. When keys differ, use `X-Router-Session-Id` on both admin and proxy requests to correlate.
- **Model IDs:** Canonical form `<provider>+<model>`. `model_aliases` maps short names to canonical IDs. `/v1/models` returns only models from `providers.models` (and aliases), not full upstream catalogs.
- **No request/usage logging to DB in MVP.** Observability is via health endpoint and Config API only.

---

## 7. Technical Requirements

**Architecture:**
- Docker native (single container, <500MB image)
- **API Server (FastAPI), two surfaces on the same process:**
  - **Proxy API:** `/v1/*` — OpenAI-compatible (models, chat/completions, embeddings). Auth: **ROUTER_CLIENT_KEY** (Bearer).
  - **Config API:** `/admin/*` — routing config, provider add/list/remove/update, credit, overrides. Auth: **ROUTER_ADMIN_KEY** (Bearer or X-API-Key). **Ideally bindable to localhost-only.** CLI and SMCP plugins (outside container) call this over HTTP. Default router port is **configurable and non-standard** (e.g. 8480) to avoid self-loop; Docker maps it to host.
- Routing Engine, Provider Adapters (with capability flags), Credit Monitor, Analytics
- **SMCP/UCW:** Ship SMCP plugins; CLI and plugins call Config API. CLI wrapable via UCW for SMCP plugin generation.
- **Local SQLite DB:** provider definitions (credentials encrypted at rest), routing config, failover conditions, agent overrides. No request logging to DB. No plaintext secrets in DB. **Path:** e.g. `/data/router.db`; **must mount `/data`** (or configured data dir) as a persistent Docker volume so state survives container restarts.
- Healthcheck endpoint for Docker orchestration

**Ecosystem & references:**
- **SMCP** — [sanctumos/smcp](https://github.com/sanctumos/smcp): plugin-based MCP server for Sanctum/Animus/Letta; plugins live in a directory (e.g. `MCP_PLUGINS_DIR`), each with `cli.py` etc. Router ships plugins for this server; we do not ship the server itself.
- **UCW** — [actuallyrizzn/ucw](https://github.com/actuallyrizzn/ucw): Universal Command Wrapper; parses CLI help and generates callable wrappers or MCP plugin files. Use to wrap the router CLI so its commands become SMCP tools. Primary use: as an SMCP plugin; also usable standalone for dev/testing.

**Performance:**
- Routing decision <50ms
- Overall added API latency <100ms
- Throughput 100–1000 concurrent (scalable by workers)
- Provider failover <5sec

**Reliability/Security:**
- 99.9% uptime target
- Graceful error & retry logic; circuit breaker on provider fail
- **Split auth:** ROUTER_CLIENT_KEY for `/v1/*`, ROUTER_ADMIN_KEY for `/admin/*`; rate limit both; optionally bind `/admin` to localhost-only
- No plaintext credentials in DB or logs; credentials encrypted at rest in DB

---

## 8. Non-Functional Requirements

- **Usable out-of-the-box:** Docs, CLI help, guided setup
- **Extensible:** Modular adapters for fast provider add
- **Docker/OS portable:** Linux/Mac/Windows (Dockerized)
- **Observable:** Health endpoint, config endpoint, routing/usage logs

---

## 9. Sample Configuration

Router listens on a **configurable, non-standard port** by default (e.g. **8480**) to avoid accidental self-loop or clashes with local backends. Example: router on `8480`, local OpenAI-compatible backend on a different port or host.

```yaml
# Optional: initial seed for providers (can also add via Config API). Port is configurable (default 8480).
server:
  port: 8480
  admin_bind_localhost_only: true
providers:
  venice:
    endpoint: https://api.venice.ai/v1
    api_key: ${VENICE_API_KEY}
    models: [minimax-v2.1, kimi-k2]
    priority: 1
    credit_threshold: 0.10
    supports_tools: true
    supports_streaming: true
    supports_multimodal: true
  featherless:
    endpoint: https://api.featherless.ai/v1
    api_key: ${FEATHERLESS_API_KEY}
    models: [kimi-k2, glm-4.6]
    priority: 2
    supports_tools: true
    supports_streaming: true
    supports_multimodal: true
  local:
    endpoint: http://host.docker.internal:8040/v1
    models: [gpt-4o-mini]
    priority: 3
    supports_tools: false
    supports_streaming: true
    supports_multimodal: false
routing:
  strategy: priority
  cost_optimization: true
monitoring:
  credit_check_interval: 300
```

---

## 10. Use Cases

**Credit Failover:** Venice credits exhaust—router flips to Featherless without agent restart. **Notification** = response headers (`X-Router-Provider`, optional `X-Router-Upstream-Model`) and logs/Config API visibility; no push events in MVP.

**Cost-Optimized Routing:** Simple queries sent to low-cost models, complex to best-in-class.

**Agent-Initiated Override:** Agent queries/overrides preferred provider via SMCP for a session.

**Resiliency Ladder:** Provider latency spike → router marks as degraded → reroutes until healthy.

**Ops/Agent Tuning:** Ops or agent changes failover threshold or provider order via CLI or SMCP; router picks up new rules from SQLite without restart.

---

## 11. Roadmap

### Phase 1 (MVP) — Core

- API server scaffolding
- Priority-based routing (configurable); routing logic (order, failover conditions) in SQLite
- At least 2 providers (e.g. Venice, Featherless; plus optional local/OpenRouter/Courier-style backends)
- Credit/health monitor
- CLI for provider config/add/remove/list/status and for routing logic (priority, failover rules); CLI UCW-wrapable for SMCP plugin exposure
- SMCP plugins for agent (status, override, routing logic); dev: run SMCP server (sanctumos/smcp) for testing; ship: plugins only, no MCP server in image
- Full OpenAI HTTP API including `/v1/models` (model listing) distinct from CLI
- Health endpoint; SQLite for routing state only (no request/usage logs in MVP)
- Dockerfile/demo compose setup

### Phase 2 (Future)

- Rule-based and complexity→capability routing
- Dashboard/UI for analytics
- Advanced SMCP and cost/budget features

---

## 12. MVP Decisions & Clarifications (for documentation)

This section locks intent for docwriters and implementers. Use it for Security/Deployment docs and to avoid re-debating fundamentals.

### Security posture (intentionally minimal; trust-based)

- Sanctum Router is designed to run **on the same machine** as Letta/Sanctum.
- **Primary security boundary is network isolation**: bind router ports to **localhost only** by default and do **not** expose them publicly.
- The Config API and SMCP write-controls are **intentionally powerful**. Documentation must include a clear warning: **loading SMCP tools with write/admin access is an intentional security hole** and should only be done in trusted/local environments.
- We are **not** implementing layered security/RBAC beyond “don’t expose ports” + simple key gating (optional). Keep it simple.

### Persistence & secrets (DB as source of truth)

- **SQLite DB in a persistent Docker volume is the single source of truth** for:
  - provider definitions
  - routing state / failover conditions
  - overrides
- Provider credentials are stored **in the DB encrypted at rest** (encryption key provided via environment).
  - **No plaintext secrets** in DB or logs.
  - Avoid storing provider keys in `.env`; the whole point is to store them safely inside the container volume once configured.

### Model IDs: namespace, not binding

- Canonical model IDs use `<provider>+<model>` to avoid collisions.
- Provider prefix is **namespacing only** — **not a binding**. Routing/failover rules decide whether a request can be served by another provider when the “preferred” one is out of credit/unhealthy/etc.
- Router should signal actual serving backend via headers: **`X-Router-Provider`** (provider id that served the request), optionally **`X-Router-Upstream-Model`** (model id as sent to that backend). **Response `model`** in chat/embeddings responses should **echo the requested model id** (canonical or alias) so OpenAI clients see stable, predictable behavior; the actual backend is indicated only via headers.
- `/v1/models` lists only **enabled/declared** models from the DB (plus aliases), not full upstream catalogs.

### Routing rules (Phase 1 = deterministic rules, not “AI complexity”)

Phase 1 routing stays simple and explicit:

- **Credit threshold failover** (works for both renewable/daily credits like Venice and depleting credits like OAI/Anthropic — the rule is still threshold-based).
- **Health-based failover** (timeouts / failing health checks mark provider unavailable).
- **Capability gating**:
  - If request includes `tools`, only route to providers with `supports_tools=true`.
  - If request is **multimodal** (images), route only to providers with `supports_vision` / `supports_multimodal=true`.
  - Streaming requests route only to providers with `supports_streaming=true`.

“Complexity estimation” and deeper cost/budget optimization remain Phase 2 unless explicitly scoped in.

### Logging / DB write load

- **No request/usage logging to DB in MVP.** No prompt or completion content is stored.
- SQLite writes are **config/state only** (providers, routing, overrides), so write load is low.

---

# Appendix: PRD Amendments Checklist

Use this checklist to tighten the PRD or track implementation. Items should be resolved in the main PRD or in a tracking doc.

## Credit Model

- [ ] For each provider, define: source of credit info (API, dashboard scrape, manual entry, adapter).
- [ ] Specify how often credit is refreshed, what happens if no credit API is available.
- [ ] “Credit threshold” meaning and source per provider.

## Task Complexity/Capability Matching

- [ ] For Phase 1: clarify if “complexity estimation” is just by model name, tokens, or deferred.
- [ ] If deferred, state explicitly: only model-request/priority in MVP.
- [ ] Full “complexity→capability” left for post–Phase 1.

## Model ID & /v1/models

- [x] **Canonical IDs:** `<provider>+<model>` (e.g. `venice+kimi-k2`). Optional `model_aliases` table for short names. **§ Full OpenAI API compatibility** and **§ Database schema**.
- [x] **/v1/models:** Returns only **enabled/declared** models (from provider config in DB), not full upstream catalogs. **§ Full OpenAI API compatibility**.
- [x] **Capability gating:** Provider flags `supports_tools`, `supports_streaming`; if request has `tools`, route only to `supports_tools=true`. In provider schema and routing logic.

## Routing Logic Control & SQLite

- [x] **Provider source of truth:** Providers (and encrypted creds) in DB; add/remove/update via Config API. Optional YAML/ENV seed at bootstrap. **§ Provider Management**, **§ Database schema**.
- [ ] SMCP/CLI semantics for `set_routing_config` (merge vs full replace; scope global).

## Full OAI Compatibility & SMCP Ship Model

- [x] **OAI:** PRD now includes **§ Full OpenAI API compatibility (reference)** with endpoints (models, chat/completions, embeddings), auth, request/response shapes, streaming, errors.
- [ ] **SMCP/UCW:** Dev: run SMCP server (sanctumos/smcp) for testing. Ship: SMCP plugins only, no MCP server in image. CLI wrapable via UCW (actuallyrizzn/ucw) for plugin generation.

## Config API (CLI/SMCP outside container)

- [x] **Config API:** PRD now includes **§ Config API (enumeration)** with base path `/admin`, auth, and full endpoint list (status, providers, credit, override, estimate-cost, routing-config GET/PUT).
- [x] **CLI/plugin config:** Require `ROUTER_URL` + `ROUTER_ADMIN_KEY` for `/admin/*`; `ROUTER_URL` + `ROUTER_CLIENT_KEY` for `/v1/*`. Canonical phrasing in §6.

## DB schema

- [x] **Schema in PRD:** PRD now includes **§ Database schema (SQLite)** with tables: `providers`, `routing_config`, `provider_priority`, `failover_conditions`, `model_aliases`, `agent_override`. No request_logs in MVP.
- [ ] Implement schema in code; document what lives in DB vs YAML (see Routing Logic Control & SQLite).

## SMCP/Agent Override & Authz

- [ ] Are all agents allowed to override routing? Is there a session/role restriction? API key?
- [ ] Abuse mitigation: can an agent always select highest-cost model?
- [ ] Specify: session-scope only; override requires ROUTER_ADMIN_KEY (or same-token correlation when keys equal).

## Agent Notification on Failover

- [ ] For Phase 1, how is failover communicated? (Response header, response body, SMCP tool event, just queryable via SMCP, etc.)

## Cost Optim/Budget Enforcement

- [ ] For Phase 1, cost logic = static price table? Budget = local config only?
- [ ] What happens when budget is hit: block, switch, alert only?

## Feature Phasing/Cut

- [ ] Make a clear “In Phase 1 / Post–Phase 1” list for each bullet in Functional Requirements.

## Sample config & port

- [x] **Port:** Router port configurable; default **non-standard** (e.g. 8480) to avoid self-loop. Sample uses `local` with `host.docker.internal:8040` instead of same port as router. **§ Sample Configuration**.
- [ ] Clarify “local” / “courier” naming in docs (generic OpenAI-compatible local endpoint).

## Uptime Target Scope

- [ ] Specify: “Router service uptime” or “router + provider,” and clarify baseline assumption.

## Encrypted Credential Storage

- [x] **Locked:** Provider credentials stored in DB **encrypted at rest** (key from environment); **no plaintext** in DB or logs. **§ Provider Management**, **§ Database schema**, **§ Reliability/Security**.

## Analytics Scope (Phase 1)

- [ ] For Phase 1: “Analytics = structured logs in SQLite or flat file, queryable via CLI. Dashboard/UI for future phase.”

## Concurrency/RAM/Scaling

- [ ] Version 1: “100–1000 concurrent on recommended hardware (~n cores/Y GB RAM); horizontally scalable via replicas.”

## Section Wording/Structure

- [ ] Clarify FastAPI as decision (not just ‘recommended’).
- [ ] Condense redundant “OpenAI-compatible” points in Key Features.
- [ ] Phase 2 one-liner added in Roadmap above.
