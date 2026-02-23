Fixed in PR (see commit below).

**#7 – SQLite connection pool (documentation)**

Documented in `router/db.py` module docstring:
- v0.1 uses no connection pool; each operation opens a new connection via `_get_conn`. Acceptable for current load.
- If traffic grows, consider a small pool or long-lived connection with locking; document concurrency assumptions.

No code change to DB layer; docs-only. Version 0.1.7.

(Ada: no additional directive; closing as implemented.)
