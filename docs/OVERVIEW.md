# Overview — What is Sanctum Router?

**Sanctum Router** is a local, self-hosted **OpenAI-compatible inference proxy**. It sits between agent frameworks (Letta/Sanctum) and multiple LLM backends (Venice, Featherless, local OpenAI-compatible servers, etc.) and provides a single stable API surface:

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`

The router chooses which backend to use **at request time**, based on deterministic policy (capabilities, credits, health), and can fail over automatically when a provider is unavailable.

---

## The "Entorhinal Cortex" concept (why this exists)

In the Sanctum stack, we model this component after the **entorhinal cortex**: a gateway between **self** and **cognition**.

- **Self** = memory/state, operational constraints, and tool-driven behavior (the agent system's continuity).
- **Cognition** = the model providers that perform inference.

Just like the entorhinal cortex mediates traffic between hippocampal memory and neocortical cognition, Sanctum Router mediates traffic between the agent and the available model substrates—selectively and predictably.

This is why routing is not "random load balancing." It's **policy-enforced gating** between identity/continuity and compute.

---

## Design goals (Phase 1 / MVP)

### 1) Single drop-in OpenAI endpoint

Any OpenAI-speaking client should work by changing only:

- **Base URL** → router URL
- **API key** → `ROUTER_CLIENT_KEY`

### 2) Deterministic routing (no "AI complexity" in MVP)

Phase 1 routing is explicit and rule-based:

- **Capability gating**
  - If the request includes `tools`, route only to providers with `supports_tools=true`
  - If the request is **multimodal** (images), route only to providers with `supports_multimodal=true`
  - If `stream: true`, route only to providers with `supports_streaming=true`

- **Health failover**
  - Providers that time out or fail health checks are skipped

- **Credit threshold failover**
  - Providers below their configured credit threshold are skipped
  - Providers with "unknown credit" can be treated as available (no threshold enforcement)

### 3) Namespace-not-binding model IDs

The router uses canonical model IDs to avoid collisions:

- **Canonical:** `<provider>+<model>` (e.g. `venice+kimi-k2`)
- **Optional aliases** (e.g. `kimi-k2` → `venice+kimi-k2`)

**Important:** provider prefixes are **namespacing**, not hard binding. If a request for `venice+kimi-k2` must fail over, the router may serve the request from another provider that declares the same upstream model name (`kimi-k2`), while still echoing the requested model id in the response for client stability.

The actual backend used is reported via response headers:

- `X-Router-Provider: <provider_id>`
- `X-Router-Upstream-Model: <model_as_sent_to_backend>` (optional)

---

## Summary

| Concept | Meaning |
|--------|---------|
| **Proxy API** | `/v1/*` — OpenAI-compatible; use `ROUTER_CLIENT_KEY`. |
| **Config API** | `/admin/*` — providers, routing, override, credit; use `ROUTER_ADMIN_KEY`. |
| **Routing** | Deterministic: capability gating + health + credit threshold; session override can pin a provider. |
| **Model IDs** | Canonical `provider+model`; aliases allowed; failover may use another provider for same upstream model. |

For control-plane details (CLI, SMCP, security), see [CONTROL_PLANE.md](CONTROL_PLANE.md). For persistence and secrets, see [PERSISTENCE_AND_SECRETS.md](PERSISTENCE_AND_SECRETS.md).
