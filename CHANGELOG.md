# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- (See open issues on the repo for audit and hardening items.)

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

[Unreleased]: https://github.com/sanctumos/sanctum-router/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.1
[0.1.0]: https://github.com/sanctumos/sanctum-router/releases/tag/v0.1.0
