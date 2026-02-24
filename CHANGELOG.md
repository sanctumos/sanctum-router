# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- (See open issues on the repo for audit and hardening items.)

## [0.1.8] - 2026-02-22

### Added

- **Provider monitor adapters:** `provider_type` in DB and Config API (POST/PATCH/GET `/admin/providers`); registry `venice` and `openai_compat`. Venice monitor uses `VENICE_BILLING_BASE_URL`, fallback order `/billing/balance` → `/billing/summary` → `/billing/usage`; OpenAI-compat returns `supported=False` (no credit). Credit loop uses monitors, last-known-good on errors; GET `/admin/credit` returns per-provider `supported`, `enforceable`, `balance`, `currency`, `below_threshold`, `as_of`, `error`. Health: GET `{endpoint}/models` with optional Bearer auth; 200→healthy, 401/403→unhealthy, 404/405→healthy, 429→unhealthy; shared `httpx.AsyncClient` from lifespan; document `--workers 1` for single-loop. Routing excludes only when `below_threshold` and `enforceable`. Bootstrap and tests for monitors, credit loop, and health semantics.

## [0.1.7] - 2026-02-23

### Changed

- **#10:** Narrow exception handling: health endpoint catches `sqlite3.Error` and `OSError`; proxy JSON parse catches `ValueError` and `TypeError`; routing_engine JSON parse catches `json.JSONDecodeError` and `TypeError`; credit_health loops re-raise `asyncio.CancelledError` and catch only `OSError`/`ValueError`/`KeyError` or `httpx.RequestError` where appropriate.
- **#7:** Document in `db.py` that v0.1 uses no connection pool; acceptable for current load; if traffic grows, consider a small pool or long-lived connection; document concurrency assumptions.
- **#11:** Document in `credit_health.py` that `run_credit_loop` and `run_health_loop` are not started by the app by default; they are plugin/external responsibility unless started from lifespan.
- **#21:** CLI boolean flags: `--supports-tools`, `--supports-streaming`, `--supports-multimodal`, and `--cost-optimization` now use a `_parse_bool` helper that correctly parses `true`/`false`/`1`/`0` (case-insensitive) instead of `type=bool` (which made `--supports-tools false` truthy).

## [0.1.6] - 2026-02-23

### Changed

- **#16:** Deduplicate server params: `get_server_params(config)` in config.py; main.py and __main__.py use it.
- **#17:** Centralize monitoring defaults (health_check_interval 60, health_check_timeout 10.0) in config; document in credit_health; document encryption key min length (16) in crypto_utils.

## [0.1.5] - 2026-02-23

### Changed

- **#15:** Extract generic `_try_candidates` in proxy; chat and embeddings use it with adapter callbacks. Reduces duplication.
- **#18:** Routing engine: `resolve_canonical_model` and `upstream_model_part` are now public API (renamed from _prefix). Improved type hints.
- **#19:** Document in routing_engine that failover_conditions are persisted for API consistency and future use; engine uses in-memory health and credit_threshold only.
- **#20:** Comment in resolve_candidates: override honored only when provider is in the available set.

## [0.1.4] - 2026-02-23

### Fixed / Documentation

- **#8:** Document in `db.provider_update` that column set is explicit; do not build from user input.
- **#13:** Clarify get_status docstring: current_provider is override for the caller's session.
- **#14:** estimate-cost: validate prompt_tokens and completion_tokens non-negative; return 400 if invalid. Document contract in docstring.

## [0.1.3] - 2026-02-23

### Documentation

- **#3:** Health check endpoint: document expected endpoint shape, add `HEALTH_CHECK_PATH` constant and docstring in `credit_health.py`.
- **#5:** Document encryption key derivation and rotation (fixed salt; key rotation requires re-encrypting provider keys) in `crypto_utils.py`.
- **#6:** README: Session override section — override per session_id; CLI vs proxy; same session required for CLI-set override to apply.
- **#9:** Docstring: GET routing-config `provider_order` is the effective routing order.
- **#12:** Docstring: PUT and PATCH routing-config both use partial-update semantics per PRD.

## [0.1.2] - 2026-02-23

### Fixed

- **Issue #2:** Require `ROUTER_ENCRYPTION_KEY` when storing provider API keys. Admin create/patch return 400 with a clear message if key is missing or too short; bootstrap raises at startup instead of silently storing NULL.
- **Issue #4:** Use constant-time comparison (`hmac.compare_digest`) for client and admin token auth to avoid timing side channels.

### Added

- `crypto_utils.encryption_available()` to check if encryption key is set. Integration test for create_provider when encryption unavailable.

## [0.1.1] - 2026-02-23

### Fixed

- **Streaming response lifecycle (Issue #1):** In streaming chat completions, the adapter no longer returns a generator that captured the HTTP response from inside an `async with` block. The stream is now fully consumed while the response is open and then yielded from a buffer, so the proxy can safely iterate without the stream being closed prematurely.

### Added

- Test suite: unit, integration, and e2e tests with ≥70% coverage (pytest, pytest-cov). Health route registered inside `create_app()` for testability.

## [0.1.0] - 2025-02-22

Initial Phase 1 release: OpenAI-compatible proxy with multi-provider routing, Config API, CLI, and SMCP plugin.

### Added

- **Proxy API** (`/v1/*`): `GET /v1/models`, `POST /v1/chat/completions`, `POST /v1/embeddings` (streaming and non-streaming). Auth via `ROUTER_CLIENT_KEY`. Response headers: `X-Router-Provider`, `X-Router-Upstream-Model`; optional pass-through of `openai-version` and `openai-processing-ms`.
- **Config API** (`/admin/*`): `GET/POST/PATCH/DELETE` providers, `GET /admin/credit`, `POST /admin/override`, `POST /admin/estimate-cost`, `GET/PUT/PATCH /admin/routing-config`, `GET /admin/status`. Auth via `ROUTER_ADMIN_KEY`. Session override via `X-Router-Session-Id` or Bearer hash.
- **Routing engine**: Priority-based provider order (DB `provider_priority` or `providers.priority`), capability gating (tools, streaming, multimodal), session override, failover on credit threshold and health. Model alias resolution; no request/usage logging to DB.
- **Database**: SQLite schema (`providers`, `routing_config`, `provider_priority`, `failover_conditions`, `model_aliases`, `agent_override`). Provider credentials encrypted at rest with `ROUTER_ENCRYPTION_KEY`. Cascade delete on provider removal.
- **Failover config**: GET/PUT/PATCH `routing-config` accepts and persists `failover` (provider_id, condition, value). GET response normalizes to PRD shape (`condition` / `value`). Routing engine does not yet read failover_conditions (in-memory credit/health only).
- **CLI** (`router.cli`): Commands for status, providers (list/add/remove), routing (get/set), override, credit. `--json` for machine output. UCW-wrapable; epilog includes "Available commands:" for help-scraping.
- **SMCP plugin** (`plugins/sanctum_router`): Tools implemented by calling router Config API. Plugin contract: `--describe` returns full JSON spec; subcommands = tool names (`get_router_status`, `list_providers`, `get_credit_status`, `select_provider`, `estimate_cost`, `get_routing_config`, `set_routing_config`). Epilog "Available commands:" for SMCP fallback discovery. Copy into SMCP `MCP_PLUGINS_DIR`; requires `ROUTER_URL` and `ROUTER_ADMIN_KEY`.
- **Config**: YAML file via `ROUTER_CONFIG`; ENV overrides for port, DB path, keys. `server.admin_bind_localhost_only` controls listen host (default true = 127.0.0.1).
- **Docker**: Dockerfile and docker-compose; single container, `/data` volume for SQLite, healthcheck on `/health`. Entrypoint `python -m router.main` so config (bind, port) is applied.
- **Docs**: README (quick start, env reference, security), PRD, Phase 1 plan, SMCP/UCW grok, gap analysis, GitHub issues review. Plugins README (SMCP contract, session correlation, security warning).

### Changed

- Config API response shapes aligned with PRD: `set_routing_config` returns `{ "ok": true, "routing_config": ... }`; `create_provider` returns `{ "ok": true, "provider": ... }`.
- GET `/admin/status` returns `current_provider` for the caller’s session (override) when request includes session (Bearer or `X-Router-Session-Id`).

### Fixed

- N/A (initial release).

### Security

- Bind to 127.0.0.1 by default. Config API and SMCP plugin have write/admin access—use only in trusted environments. Provider API keys stored encrypted in DB; require `ROUTER_ENCRYPTION_KEY` when using API keys.

[Unreleased]: https://github.com/sanctumos/sanctum-router/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.6
[0.1.5]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.5
[0.1.4]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.4
[0.1.3]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.3
[0.1.2]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.2
[0.1.1]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.1
[0.1.0]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.0
