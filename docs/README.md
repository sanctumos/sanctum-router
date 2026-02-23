# Sanctum Router — Documentation

This folder contains the full documentation set for Sanctum Router.

## Documentation index

| Document | Description |
|----------|-------------|
| **[QUICKSTART.md](QUICKSTART.md)** | Get running in minutes: Docker and local install, curl and CLI examples, adding your first provider. |
| **[OVERVIEW.md](OVERVIEW.md)** | What Sanctum Router is, the “Entorhinal Cortex” concept, and Phase 1 design goals. |
| **[CONTROL_PLANE.md](CONTROL_PLANE.md)** | Config API (`/admin/*`), CLI, SMCP plugins, and security posture. |
| **[PERSISTENCE_AND_SECRETS.md](PERSISTENCE_AND_SECRETS.md)** | SQLite, encrypted provider keys, Docker volumes, and operational notes. |
| **[REFERENCE.md](REFERENCE.md)** | Environment variables, session override, proxy and admin API summary, repo structure. |
| **[PRD.md](PRD.md)** | Product Requirements Document: positioning, full API spec, DB schema, MVP decisions. |
| **[plan.md](plan.md)** | Phase 1 implementation plan and dependency order. |

## Suggested reading order

1. **New users:** [QUICKSTART.md](QUICKSTART.md) → [OVERVIEW.md](OVERVIEW.md) → [REFERENCE.md](REFERENCE.md) (env and session override).
2. **Operators:** [CONTROL_PLANE.md](CONTROL_PLANE.md) and [PERSISTENCE_AND_SECRETS.md](PERSISTENCE_AND_SECRETS.md).
3. **Contributors / deep spec:** [PRD.md](PRD.md) and [plan.md](plan.md).
