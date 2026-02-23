# Persistence and secrets

Sanctum Router uses a **SQLite database** as the single source of truth for providers and routing config. In Docker, the DB lives on a **persistent volume** so state survives container restarts. Provider API keys are **encrypted at rest** and only decrypted in memory when making upstream calls.

---

## SQLite and Docker volume

- **Path:** Configurable via `ROUTER_DB_PATH` (default in Docker: `/data/router.db`).
- **Docker:** The compose file mounts a volume at `/data`. Always use a volume so the DB is not lost on container restart.
- **Concurrency:** In Phase 1 (v0.1), each operation opens a new connection; there is no connection pool. This is acceptable for current load. If traffic grows, consider a small pool or long-lived connection and document concurrency assumptions.

---

## Encrypted provider keys

- Provider API keys are stored **encrypted** in the `providers` table. Encryption uses **ROUTER_ENCRYPTION_KEY** from the environment (format and minimum length depend on implementation; see `router/crypto_utils.py`).
- Keys are **decrypted only in memory** when the router forwards requests to a provider. No plaintext secrets are written to DB or logs.
- If you add or update a provider with an `api_key` via the Config API, **ROUTER_ENCRYPTION_KEY** must be set and valid, or the router returns 400. Bootstrap from YAML also requires the encryption key when provider keys are present.

---

## What is stored

- **Providers:** id, endpoint, encrypted api_key, models (JSON), priority, credit_threshold, capability flags (supports_tools, supports_streaming, supports_multimodal), healthy flag.
- **Routing config:** strategy, provider_order, failover conditions.
- **Model aliases:** short name → canonical `provider+model`.
- **Session override:** session_id → provider_id (for pinning a provider per session).

There is **no request/usage logging to the DB** in the MVP; observability is via the health endpoint and Config API only.

---

## Backup and migration

- Back up the **volume** (or the file at `ROUTER_DB_PATH`) to preserve providers, routing, and encrypted keys. Restore by mounting the same volume or copying the file and setting `ROUTER_DB_PATH`.
- Key rotation: changing **ROUTER_ENCRYPTION_KEY** requires re-encrypting provider keys (export/re-import or in-place re-encryption if implemented). See `router/crypto_utils.py` for derivation/rotation notes in docstrings.
