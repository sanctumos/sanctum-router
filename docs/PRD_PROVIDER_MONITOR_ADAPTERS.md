# Provider Monitor Adapters (Credit / RateLimit / Health) — Phase 1

**Secondary PRD.** This document specifies how the Router obtains per-provider credit, rate-limit, and (optionally) health data from provider-specific APIs. It generalizes a thin-client + normalize pattern so each provider can be monitored without SDK dependencies or runtime plugin loading.

**Source of truth for product scope:** [PRD.md](PRD.md). This PRD defines the **adapter architecture** that fulfills the Router’s credit-awareness and health requirements.

---

## 1. Goals and non-goals

### Goals

- **Thin, dependency-light clients** per provider: HTTP only (no full provider SDKs). Router uses a single HTTP client (e.g. `httpx`) for all monitor calls.
- **Provider-specific endpoints** for billing/usage and (where available) rate limits; raw fetch → **normalized parse** into a standard internal schema the Router consumes.
- **Fallback behavior** when a provider’s credit/billing endpoint is missing or fails (e.g. use usage API when summary is unavailable).
- **Pure, cacheable outputs:** Normalization returns stable keys; results can be cached in memory with TTL and used for routing/failover decisions.
- **Registry-based “plugin” architecture without runtime loading:** Provider type is a string in config/DB; a fixed registry maps type → monitor instance. No dynamic import or plugin packaging in Phase 1.

### Non-goals (Phase 1)

- Dynamic loading of third-party monitor plugins from disk or network.
- Full provider SDKs as dependencies.
- Persisting raw provider API responses to DB or logs.
- Rate-limit–based routing or gating (only credit and health drive failover in Phase 1; rate-limit schema is specified for future use).

---

## 2. Reference architecture: Venice thin client

The following pattern is the **exemplar** for each provider monitor adapter:

1. **Transport layer (thin client)**  
   - `get_*()` functions that call provider-specific HTTP endpoints.  
   - No SDK dependency; use `httpx` (async) or equivalent.  
   - Fixed timeouts (e.g. 30s).  
   - Clear error handling: catch HTTP/network errors; do not crash the monitor loop.

2. **Normalization layer**  
   - `parse_*()` functions that convert provider-specific JSON into the **standard internal schema** (see § 3).  
   - All provider-specific field names and shapes stay inside the adapter module.

3. **Fallback behavior**  
   - When the “preferred” endpoint is unavailable (e.g. 404 or 5xx), fall back to an alternative when the provider offers one (e.g. `/billing/summary` → `/billing/usage`).  
   - If no credit API exists, return a status with `supported=False`.

4. **Containment**  
   - Provider-specific quirks (e.g. Diem vs USD, array vs object usage payloads) are handled only inside that provider’s adapter. The Router and credit loop see only the normalized schema.

**Implementation note:** Inside the Router (FastAPI), use **`httpx`** for async compatibility. Do **not** log or expose raw payloads by default; only normalized fields are returned via `/admin/credit` and used for threshold comparison.

---

## 3. Standard internal schemas

The Router consumes these shapes. All adapters must map provider responses into them.

### 3.1 CreditStatus (required for Phase 1)

```python
CreditStatus = {
    "supported": bool,              # False when provider has no credit/billing API
    "balance": float | None,         # Normalized numeric balance if known
    "currency": str | None,         # e.g. "diem", "usd"
    "below_threshold": bool | None, # Computed when balance and threshold are known
    "as_of": str,                   # ISO timestamp of the fetch
    "raw": dict | None              # Optional; must not be logged or exposed via API
}
```

- **supported:** `True` only if the provider exposes a billing/credit endpoint we can call. When `False`, the Router does **not** enforce credit threshold for this provider (see § 6).
- **balance:** "Remaining credit" in the provider's native unit where possible (preferred). If only spend is available, adapter should set `balance=None` and `supported=True` (unknown remaining), unless the provider also provides an allocation limit to compute remaining. Single numeric value the Router uses for threshold comparison.
- **currency:** Informational only in Phase 1 (e.g. for display in `/admin/credit`).
- **below_threshold:** Set by the Router after comparing `balance` to the provider’s `credit_threshold`; adapters may leave it `None` and let the Router compute it.
- **as_of:** When this status was obtained (for caching and debugging).
- **raw:** If present, must never be written to logs or returned in the public Config API response.

**Units:** `credit_threshold` is interpreted in the same unit/currency as `CreditStatus.balance` for that provider (e.g. Diem for Venice). If a provider reports balance in multiple currencies, the adapter must choose one and report that currency consistently so ops do not confuse units (e.g. setting "0.10" thinking USD while balance is in Diem).

### 3.2 RateLimitStatus (optional, Phase 1)

Reserved for future use. No routing decisions in Phase 1.

```python
RateLimitStatus = {
    "requests_per_minute": int,
    "requests_per_day": int,
    "tokens_per_minute": int,
    "tokens_per_day": int,
    "next_epoch": str | None,
    "per_model": [{"model": str, "rpm": int, "rpd": int, "tpm": int}],
    "as_of": str,
}
```

### 3.3 HealthStatus and generic health check (Phase 1)

Phase 1 health is implemented by the Router as a **generic health check**; a per-provider health adapter is optional and can be added later. No HealthStatus schema is mandated here; the existing in-memory `healthy: bool` per provider remains sufficient.

**Generic health check (Phase 1):** `GET {endpoint}/models` (OpenAI-style). Standardize storage so that **provider `endpoint` is stored as a base that includes `/v1`** (e.g. `https://api.example.com/v1`). Then the health path is always **`/models`** (i.e. `GET {endpoint}/models`). Do not alternate between `/v1/models` and `/models` by convention; lock to one. Recommendation: store endpoints as `.../v1` base, then health path = `/models`.

- **Auth:** Health check requests MUST include the provider's upstream auth header (e.g. `Authorization: Bearer <provider_api_key>`) when a key is configured. Otherwise unauthenticated checks will get 401s and incorrectly mark healthy providers as unhealthy.

**Response-code semantics:** So no one “kills” a provider because it doesn’t implement `/models`: **200** → healthy; **401/403** → unhealthy (credentials missing/invalid, not usable anyway); **404/405** → “health check unsupported” (do not flip to unhealthy; rely on request failures to exclude the provider); **≥500 / timeout / connection error** → unhealthy (transient).

---

## 4. Provider type and registry

### 4.1 Provider type field

Each provider has a **provider type** string that selects which monitor adapter to use:

- **In the DB:** Add a column `provider_type TEXT` to the `providers` table. Values: `venice`, `openai_compat`, `featherless`, `openrouter`, etc.
- **Default:** If `provider_type` is missing or not in the registry, use `openai_compat` (no credit API).
- **Config API and bootstrap:** The main PRD Config API (POST/PATCH `/admin/providers`, GET response) and any YAML/ENV seed at bootstrap **must** include `provider_type` as a first-class field so the monitor registry is usable; otherwise the swarm will implement monitors without a way to set type per provider.

### 4.2 Adapter interface

The Router defines a protocol that each monitor adapter implements:

```python
from typing import Protocol
from datetime import datetime

class ProviderMonitor(Protocol):
    async def get_credit_status(self, provider: Provider, now: datetime) -> CreditStatus:
        """Fetch and normalize credit/billing for this provider. Return supported=False if no API."""
        ...
```

- **Provider** here is the Router’s provider model (id, endpoint, api_key decrypted, credit_threshold, etc.).
- **now** is passed so adapters can set `as_of` consistently and so tests can inject time.

Optional methods (Phase 1 can stub or omit):

- `get_rate_limit_status(self, provider: Provider, now: datetime) -> RateLimitStatus | None`
- `get_health_status(self, provider: Provider, now: datetime) -> HealthStatus | None`

### 4.3 Registry / factory

- **No dynamic plugin loading.** A fixed registry in code:

```python
PROVIDER_MONITORS: dict[str, ProviderMonitor] = {
    "venice": VeniceMonitor(),
    "openai_compat": OpenAICompatMonitor(),
    "featherless": FeatherlessMonitor(),  # if implemented
    "openrouter": OpenRouterMonitor(),    # if implemented
}
```

- **Lookup:** When the credit loop (or health loop) runs for a provider, it reads `provider_type` from the DB. If the key is missing from `PROVIDER_MONITORS`, use `openai_compat`.
- **OpenAICompatMonitor:** Always returns `CreditStatus(supported=False, balance=None, ...)`. No HTTP call. Router will not enforce credit threshold for this type (see § 6).

---

## 5. Caching policy

- **In-memory only** in Phase 1. No Redis or DB cache for monitor responses.
- **TTL:** Configurable per adapter or global (e.g. 60–300 seconds). Cached value is used until TTL expires, then the adapter is called again.
- **Last-known-good / stale policy:** On fetch failure, keep the previous cached `CreditStatus` for up to **N** consecutive failed intervals (e.g. N=2 or 3). Expose **`as_of`** in the normalized status (and in `/admin/credit`) so the operator can see staleness. After N failures without a successful refresh, leave state unchanged but `as_of` reflects the last successful fetch; do not mark the provider unhealthy solely due to credit fetch failure.
- **Credit loop:** The existing `run_credit_loop` (or equivalent) calls the appropriate monitor per provider, updates in-memory balance and `below_threshold`, and exposes the result via `get_all_credit_state()` → `/admin/credit`. Caching can be implemented inside the monitor or in the loop (e.g. skip fetch if cache is fresh).

---

## 6. Failure semantics

- **When the Router enforces threshold:** The Router enforces credit threshold only when **`supported=True` and `balance` is not `None`**. If either is false/missing, do not exclude the provider from routing on credit grounds; only health and explicit failover rules apply.
- **Unsupported credit:** When `get_credit_status` returns `supported=False`, the Router **must not** enforce credit threshold for that provider.
- **Fetch error (network, 5xx, timeout):** Do not overwrite the last known good balance with an error; retain previous balance per §5 (last-known-good). It's fine for the status to become stale (`as_of` stops updating) and optionally surface an `error` field in `/admin/credit`. Do not mark the provider unhealthy solely due to credit fetch failure (health is separate). “stale” the provider unhealthy solely due to credit fetch failure (health is separate).
- **Malformed response:** If the adapter cannot parse the response, return `CreditStatus(supported=True, balance=None, ...)` so the Router treats balance as unknown and does not enforce threshold (or treats as “below threshold” only if policy says “unknown = exclude”; Phase 1 recommendation: unknown = do not enforce).

---

## 7. Security notes

- **Provider API keys (billing scope):** Monitor adapters use the **provider’s** API key (decrypted in memory) to call the provider’s billing/usage endpoints. That key often needs billing/read-only scope. This is distinct from `ROUTER_ADMIN_KEY`, which only authenticates access to the Router's own `/admin/*` Config API and is never sent upstream.
- **Do not log or expose raw payloads:** The `raw` field in `CreditStatus`, if present, must never be written to application logs or returned in `/admin/credit`. Only normalized fields (`balance`, `currency`, `below_threshold`, `as_of`) are exposed. **Optional (implementation detail):** the Router may add a non-schema field to the `/admin/credit` response per provider, e.g. `error: null | "timeout" | "http_403" | "parse_error"`, to aid ops debugging without changing the `CreditStatus` schema.
- **Secrets in memory only:** Decrypted API keys are used only for the duration of the request inside the Router process; they are not logged or sent to any other service.

---

## 8. What to copy from the Venice reference script

When implementing the Venice adapter (and others), explicitly apply these patterns:

| Pattern | Requirement |
|--------|-------------|
| No SDK dependency | Use only `httpx` (or similar) for HTTP. No Venice SDK. |
| Timeouts | Use a fixed timeout (e.g. 30s) on every request. |
| Error handling with fallback | If `/billing/summary` returns 4xx/5xx, fall back to `/billing/usage` and derive a summary. |
| Normalization function | A `parse_*()` (or equivalent) that returns the standard `CreditStatus` shape with stable keys. |
| Provider-specific weirdness contained | All Venice-specific field names and response shapes stay in the Venice adapter module. |

---

## 9. Adapter matrix (Phase 1)

| provider_type     | Credit API | Rate limit API | Health | Notes |
|-------------------|------------|----------------|--------|--------|
| **venice**        | Yes        | Yes (optional) | Generic | Use `/billing/usage`, `/billing/summary`, `/billing/balance`; fallback as in reference. Venice billing endpoints may require an API key with billing scope. |
| **openai_compat** | No         | No             | Generic | `get_credit_status` returns `supported=False`. Router uses generic GET for health. |
| **featherless**   | TBD        | TBD            | Generic | Implement if Featherless exposes billing/usage; otherwise same as openai_compat. |
| **openrouter**    | TBD        | TBD            | Generic | Often no public credit API; default to `supported=False` unless documented. |
| **ollama**        | No         | No             | Generic | Local; no credit. Use openai_compat. |

**Generic health:**Router’Use the standardized health check from §3.3: store `endpoint` as `.../v1`, then `GET {endpoint}/models`.

---

## 10. Summary

- **Thin client + normalize** per provider, with **httpx**, timeouts, and fallback.
- **Standard schema:** `CreditStatus` (required); `RateLimitStatus` / `HealthStatus` optional.
- **Provider type** in DB; **registry** `PROVIDER_MONITORS[provider_type]`; default `openai_compat` (no credit).
- **Caching:** In-memory, TTL, last-known-good for up to N failed intervals; expose `as_of` for staleness.
- **Failure semantics:** Enforce threshold only when `supported=True` and `balance` is not `None`; unsupported or unknown credit ⇒ do not enforce; fetch errors do not mark provider unhealthy.
- **Security:** No raw payloads in logs or API; admin/provider keys only in memory for the request.

This gives the Router a clear, implementable “provider monitor adapter” design that matches the Venice reference and keeps Phase 1 simple and secure.
