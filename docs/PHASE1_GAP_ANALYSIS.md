# Phase 1 Plan/PRD vs Implementation — Gap Analysis

This document compares the [Phase 1 implementation plan](.cursor/plans/sanctum_router_phase_1_implementation_7ccc53d4.plan.md) (and [PRD](PRD.md)) to the current sanctum-router implementation and lists what was **left out or skipped**. It does not cover intentionally deferred PRD appendix items (e.g. agent authz, budget enforcement, analytics scope).

---

## 1. Failover conditions: no write path (skipped)

**Plan 8.10:** “Update routing_config singleton and **provider_priority / failover_conditions** tables; return updated config.”

**PRD § Config API:** PUT/PATCH `/admin/routing-config` — “**Request:** Same shape as GET response (partial for PATCH).” GET response includes `failover`: `[ { "provider_id", "condition": "credit_threshold"|"health", "value"?: ... } ]`.

**Implementation:**

- **GET** `/admin/routing-config` returns `failover` from `db.failover_conditions_get_all()` ✓  
- **PUT/PATCH** `/admin/routing-config` body only has `strategy`, `cost_optimization`, `provider_order`. **No `failover` field;** failover_conditions are never written via the API.
- **Routing engine** does not use `failover_conditions` for decisions; it uses in-memory credit/health from `credit_health` and `providers.credit_threshold`. So the table is persisted and readable but has no write path and no effect on routing.

**Gap:** Accept and persist `failover` in PUT/PATCH `/admin/routing-config` (and optionally have routing engine respect it in a later iteration). DB layer already has `failover_conditions_set` and `failover_conditions_delete_for_provider`.

**SMCP/CLI:** Plugin `set_routing_config` only passes strategy and provider_order; no failover (because API doesn’t support it).

---

## 2. Optional proxy response headers (recommended, not done)

**PRD § Full OpenAI API compatibility:** “Optional headers (recommended): Echo or set **openai-version** and **openai-processing-ms** where applicable so clients that rely on them do not break.”

**Implementation:** Proxy sets `X-Router-Provider` and `X-Router-Upstream-Model` only. It does not echo or set `openai-version` or `openai-processing-ms` from upstream responses.

**Gap:** Minor; add pass-through (or set) of these headers when present in upstream response (and optionally set processing-ms from elapsed time).

---

## 3. Config API response shapes (minor)

**PRD:**

- PUT/PATCH `/admin/routing-config` — “**Response:** `{ "ok": true, "routing_config": { ... } }`.”
- POST `/admin/providers` — “**Response:** `{ "ok": true, "provider": { ... } }`.”

**Implementation:**

- `set_routing_config` returns the config object directly (same as GET), not `{ "ok": true, "routing_config": { ... } }`.
- `create_provider` returns `{ "id", "endpoint", "priority" }` only, not `{ "ok": true, "provider": { ... } }` and not the full provider object.

**Gap:** Optional consistency with PRD: wrap routing-config response; return full provider object (no key) in create response.

---

## 4. Bind address not driven by config

**Plan 1.3:** Config includes `server.admin_bind_localhost_only`. **Plan 1.5:** Bind whole router to 127.0.0.1 by default.

**Implementation:** `main.py` and Dockerfile hardcode `host="127.0.0.1"`. The config key `server.admin_bind_localhost_only` is loaded in `config.py` but never used to choose bind address (e.g. 0.0.0.0 when false).

**Gap:** For Phase 1 this is acceptable (default is localhost-only). If future deployment needs binding to 0.0.0.0, use `server.admin_bind_localhost_only` (or a dedicated `server.bind`) to select host.

---

## 5. GET /admin/status — current_provider

**PRD:** Response may include “current_provider?”.

**Implementation:** Always returns `current_provider: null`. There is no “global” current provider; override is per-session. So this is consistent for MVP; a future enhancement could optionally take a session (e.g. query param or header) and return that session’s override as current_provider.

---

## 6. Estimate-cost behavior

**PRD:** “Response: estimated_cost?, currency?, model, tokens.” **Plan 8.8:** “MVP: can return placeholder or static table lookup.”

**Implementation:** Returns `estimated_cost: 0.0`, `currency: "USD"`, `model`, `tokens`. No static table or real pricing. **No gap** for Phase 1; explicitly placeholder.

---

## 7. PRD appendix items (intentionally open)

These are PRD checklist items, not implementation bugs:

- Failover communication (header vs body vs SMCP event).
- SMCP/CLI semantics for `set_routing_config` (merge vs full replace).
- Agent override authz (who can override; abuse mitigation).
- Cost/budget: static table, budget hit behavior.
- Analytics scope (logs vs dashboard).
- Sample config “local”/“courier” naming.

They are left as product/design decisions; implementation is consistent with “Phase 1 MVP” as scoped in the plan.

---

## Summary

| Item | Severity | Action |
|------|----------|--------|
| Failover conditions not writable via PUT/PATCH routing-config | **Medium** | Add `failover` to `RoutingConfigBody`; persist via existing DB helpers; optionally use in routing later. |
| openai-version / openai-processing-ms not echoed | Low | Pass through (or set) in proxy responses when available. |
| routing-config/providers response shape vs PRD | Low | Optionally wrap and align with PRD table. |
| admin_bind_localhost_only not used | Low | Use when adding configurable bind address. |
| current_provider always null | Info | Acceptable for MVP; enhance later if needed. |

The only substantive functional gap is **failover_conditions** having no API write path and no use in routing logic, despite the plan and PRD describing updates to that table and a request body that matches the GET response shape.
