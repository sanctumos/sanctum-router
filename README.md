# Sanctum Router

**OpenRouter’s role—but local, extensible, and wired into the agent stack.** A self-hosted, OpenAI-compatible inference proxy that routes agent LLM requests across multiple providers (Venice.ai, Featherless.ai, local backends, etc.) with credit-aware failover, capability gating, and full control via Config API and SMCP plugins.

- **Self-hosted:** You run it; you own data, control, and logs.
- **Agent/ops integrated:** SMCP plugins and CLI let agents and ops query or update routing, providers, and overrides at runtime.
- **Capability-aware:** Route by tools, streaming, and multimodal support—not just model string.
- **Single source of truth:** Provider definitions, routing state, and failover rules live in a local SQLite DB (credentials encrypted at rest).

## Docs

- **[Product Requirements Document (PRD)](docs/PRD.md)** — Positioning, full OAI/Config API spec, DB schema, MVP decisions, and handoff checklist.

## Repo structure

```
sanctum-router/
├── README.md           # This file
├── LICENSE             # AGPL-3.0 (code)
├── LICENSE-DOCS        # CC-BY-SA 4.0 (documentation and other non-code materials)
└── docs/
    └── PRD.md          # Product requirements and technical spec
```

## Licenses

- **Code:** [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).
- **Documentation and other non-code materials:** [Creative Commons Attribution-ShareAlike 4.0 International](LICENSE-DOCS) (CC-BY-SA 4.0). See [LICENSE-DOCS](LICENSE-DOCS) and the [CC-BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode).

## Contributing

Contributions are welcome. By contributing code, you agree to license it under AGPL-3.0. Documentation and non-code contributions are under CC-BY-SA 4.0.
