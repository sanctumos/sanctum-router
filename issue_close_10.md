Fixed in PR (see commit below).

**#10 – Narrow exception handling**

- **main.py** `/health`: catch only `sqlite3.Error` and `OSError` for DB/file errors instead of bare `Exception`.
- **proxy.py** chat/embeddings: `request.json()` failures caught as `ValueError` and `TypeError` (invalid JSON / body).
- **routing_engine.py** parsing `models_raw`: catch `json.JSONDecodeError` and `TypeError` instead of `Exception`.
- **credit_health.py** `run_credit_loop` / `run_health_loop`: re-raise `asyncio.CancelledError`; catch only `OSError`, `ValueError`, `KeyError` (and in fetcher/health: `httpx.RequestError`) so CancelledError is not silenced.
- **credit_health.py** `_check_health`: catch `OSError` and `httpx.RequestError` instead of broad `Exception`.

Unit test for `_check_health` updated to raise `httpx.RequestError` so the narrowed handling is covered.

All tests green; coverage ≥70%. Version bumped to 0.1.7.

(Ada: no additional directive; closing as implemented.)
