Fixed in PR (see commit below).

**#11 – Credit/health loops (documentation)**

Documented in `router/credit_health.py`:
- `run_credit_loop` and `run_health_loop` docstrings now state they are **not** started by the app by default; they are plugin/external responsibility unless started from lifespan (e.g. with intervals from config).

Docs-only; no change to lifespan. Version 0.1.7.

(Ada: no additional directive; closing as implemented.)
