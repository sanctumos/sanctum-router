"""
SQLite data access layer. PRD § Database schema.
No request_logs table; no request/usage logging to DB in Phase 1.
PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL.

Concurrency: each operation opens a new connection (_get_conn). No connection pool; acceptable for v0.1.
If traffic grows, consider a small pool or long-lived connection with locking; document concurrency assumptions.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

# Default path; override with ROUTER_DB_PATH
DEFAULT_DB_PATH = os.environ.get("ROUTER_DB_PATH", "/data/router.db")

SCHEMA_SQL = """
-- Provider definitions (single source of truth). Credentials encrypted at rest.
CREATE TABLE IF NOT EXISTS providers (
  id TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL,
  api_key_encrypted BLOB,
  provider_type TEXT,
  models TEXT NOT NULL,
  priority INTEGER NOT NULL,
  credit_threshold REAL,
  supports_tools INTEGER NOT NULL DEFAULT 1,
  supports_streaming INTEGER NOT NULL DEFAULT 1,
  supports_multimodal INTEGER NOT NULL DEFAULT 0,
  healthy INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS routing_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  strategy TEXT NOT NULL DEFAULT 'priority',
  cost_optimization INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS provider_priority (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL UNIQUE REFERENCES providers(id),
  priority_order INTEGER NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS failover_conditions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL REFERENCES providers(id),
  condition_type TEXT NOT NULL,
  threshold_value REAL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_aliases (
  alias TEXT PRIMARY KEY,
  canonical_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_override (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL UNIQUE,
  provider_id TEXT REFERENCES providers(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO routing_config (id, strategy, cost_optimization, updated_at)
VALUES (1, 'priority', 0, datetime('now'));
"""


def get_db_path() -> str:
    path = os.environ.get("ROUTER_DB_PATH", DEFAULT_DB_PATH)
    return path


def ensure_db_dir() -> None:
    path = get_db_path()
    dirpath = Path(path).parent
    if dirpath.name:
        dirpath.mkdir(parents=True, exist_ok=True)


def _migrate_provider_type(conn: sqlite3.Connection) -> None:
    """If providers table exists but provider_type column is missing, add it (existing rows get NULL)."""
    cursor = conn.execute("PRAGMA table_info(providers)")
    columns = [row[1] for row in cursor.fetchall()]
    if "provider_type" not in columns:
        conn.execute("ALTER TABLE providers ADD COLUMN provider_type TEXT")


def init_db(db_path: Optional[str] = None) -> None:
    """Create DB and schema if not present. Idempotent. Set WAL + synchronous=NORMAL."""
    path = db_path or get_db_path()
    ensure_db_dir()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.executescript(SCHEMA_SQL)
    _migrate_provider_type(conn)
    conn.commit()
    conn.close()


def _get_conn():
    ensure_db_dir()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# --- Providers ---

def _normalize_provider_type(raw: Any) -> str:
    """Treat NULL or empty provider_type as openai_compat."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "openai_compat"
    return str(raw).strip()


def provider_list() -> list[dict[str, Any]]:
    with _get_conn() as c:
        rows = c.execute(
            "SELECT id, endpoint, api_key_encrypted, provider_type, models, priority, credit_threshold, "
            "supports_tools, supports_streaming, supports_multimodal, healthy, updated_at FROM providers"
        ).fetchall()
        return [
            {
                "id": r["id"],
                "endpoint": r["endpoint"],
                "api_key_encrypted": r["api_key_encrypted"],
                "provider_type": _normalize_provider_type(r["provider_type"]),
                "models": r["models"] if isinstance(r["models"], str) else json.dumps(r["models"]),
                "priority": r["priority"],
                "credit_threshold": r["credit_threshold"],
                "supports_tools": bool(r["supports_tools"]),
                "supports_streaming": bool(r["supports_streaming"]),
                "supports_multimodal": bool(r["supports_multimodal"]),
                "healthy": bool(r["healthy"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]


def provider_get(provider_id: str) -> Optional[dict[str, Any]]:
    with _get_conn() as c:
        r = c.execute(
            "SELECT id, endpoint, api_key_encrypted, provider_type, models, priority, credit_threshold, "
            "supports_tools, supports_streaming, supports_multimodal, healthy, updated_at FROM providers WHERE id = ?",
            (provider_id,),
        ).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "endpoint": r["endpoint"],
            "api_key_encrypted": r["api_key_encrypted"],
            "provider_type": _normalize_provider_type(r["provider_type"]),
            "models": r["models"] if isinstance(r["models"], str) else json.dumps(r["models"]),
            "priority": r["priority"],
            "credit_threshold": r["credit_threshold"],
            "supports_tools": bool(r["supports_tools"]),
            "supports_streaming": bool(r["supports_streaming"]),
            "supports_multimodal": bool(r["supports_multimodal"]),
            "healthy": bool(r["healthy"]),
            "updated_at": r["updated_at"],
        }


def provider_insert(
    id: str,
    endpoint: str,
    api_key_encrypted: Optional[bytes],
    models: str,
    priority: int,
    credit_threshold: Optional[float] = None,
    provider_type: Optional[str] = None,
    supports_tools: int = 1,
    supports_streaming: int = 1,
    supports_multimodal: int = 0,
) -> None:
    models_str = models if isinstance(models, str) else json.dumps(models)
    with _get_conn() as c:
        c.execute(
            """INSERT INTO providers (id, endpoint, api_key_encrypted, provider_type, models, priority, credit_threshold,
            supports_tools, supports_streaming, supports_multimodal, healthy, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))""",
            (id, endpoint, api_key_encrypted, provider_type if provider_type and provider_type.strip() else None, models_str, priority, credit_threshold,
             supports_tools, supports_streaming, supports_multimodal),
        )


def provider_update(
    provider_id: str,
    *,
    endpoint: Optional[str] = None,
    api_key_encrypted: Optional[bytes] = None,
    provider_type: Optional[str] = None,
    models: Optional[str] = None,
    priority: Optional[int] = None,
    credit_threshold: Optional[float] = None,
    supports_tools: Optional[int] = None,
    supports_streaming: Optional[int] = None,
    supports_multimodal: Optional[int] = None,
    healthy: Optional[int] = None,
) -> None:
    """Update only the provided columns. Column set is explicit (this signature); do not build column names from user input."""
    updates = ["updated_at = datetime('now')"]
    args: list[Any] = []
    if endpoint is not None:
        updates.append("endpoint = ?")
        args.append(endpoint)
    if api_key_encrypted is not None:
        updates.append("api_key_encrypted = ?")
        args.append(api_key_encrypted)
    if provider_type is not None:
        updates.append("provider_type = ?")
        args.append(provider_type if provider_type.strip() else None)
    if models is not None:
        updates.append("models = ?")
        args.append(models if isinstance(models, str) else json.dumps(models))
    if priority is not None:
        updates.append("priority = ?")
        args.append(priority)
    if credit_threshold is not None:
        updates.append("credit_threshold = ?")
        args.append(credit_threshold)
    if supports_tools is not None:
        updates.append("supports_tools = ?")
        args.append(supports_tools)
    if supports_streaming is not None:
        updates.append("supports_streaming = ?")
        args.append(supports_streaming)
    if supports_multimodal is not None:
        updates.append("supports_multimodal = ?")
        args.append(supports_multimodal)
    if healthy is not None:
        updates.append("healthy = ?")
        args.append(healthy)
    args.append(provider_id)
    with _get_conn() as c:
        c.execute(f"UPDATE providers SET {', '.join(updates)} WHERE id = ?", args)


def provider_delete(provider_id: str) -> None:
    """Cascade: provider_priority, failover_conditions, agent_override where provider_id = id."""
    with _get_conn() as c:
        c.execute("DELETE FROM provider_priority WHERE provider_id = ?", (provider_id,))
        c.execute("DELETE FROM failover_conditions WHERE provider_id = ?", (provider_id,))
        c.execute("DELETE FROM agent_override WHERE provider_id = ?", (provider_id,))
        c.execute("DELETE FROM providers WHERE id = ?", (provider_id,))


def provider_count() -> int:
    with _get_conn() as c:
        return c.execute("SELECT COUNT(*) FROM providers").fetchone()[0]


# --- routing_config ---

def routing_config_get() -> dict[str, Any]:
    with _get_conn() as c:
        r = c.execute("SELECT strategy, cost_optimization, updated_at FROM routing_config WHERE id = 1").fetchone()
        if not r:
            return {"strategy": "priority", "cost_optimization": 0, "updated_at": None}
        return {"strategy": r["strategy"], "cost_optimization": r["cost_optimization"], "updated_at": r["updated_at"]}


def routing_config_set(strategy: Optional[str] = None, cost_optimization: Optional[int] = None) -> None:
    updates = ["updated_at = datetime('now')"]
    args: list[Any] = []
    if strategy is not None:
        updates.append("strategy = ?")
        args.append(strategy)
    if cost_optimization is not None:
        updates.append("cost_optimization = ?")
        args.append(cost_optimization)
    if args:
        with _get_conn() as c:
            c.execute(f"UPDATE routing_config SET {', '.join(updates)} WHERE id = 1", args)


# --- provider_priority ---

def provider_priority_get_all() -> list[tuple[str, int]]:
    with _get_conn() as c:
        rows = c.execute("SELECT provider_id, priority_order FROM provider_priority ORDER BY priority_order").fetchall()
        return [(r["provider_id"], r["priority_order"]) for r in rows]


def provider_priority_set(provider_id: str, priority_order: int) -> None:
    with _get_conn() as c:
        c.execute(
            """INSERT INTO provider_priority (provider_id, priority_order, updated_at)
            VALUES (?, ?, datetime('now')) ON CONFLICT(provider_id) DO UPDATE SET
            priority_order = excluded.priority_order, updated_at = datetime('now')""",
            (provider_id, priority_order),
        )


def provider_priority_delete(provider_id: str) -> None:
    with _get_conn() as c:
        c.execute("DELETE FROM provider_priority WHERE provider_id = ?", (provider_id,))


# --- failover_conditions ---

def failover_conditions_get_all() -> list[dict[str, Any]]:
    with _get_conn() as c:
        rows = c.execute(
            "SELECT id, provider_id, condition_type, threshold_value, updated_at FROM failover_conditions"
        ).fetchall()
        return [dict(r) for r in rows]


def failover_conditions_set(provider_id: str, condition_type: str, threshold_value: Optional[float] = None) -> None:
    with _get_conn() as c:
        c.execute(
            """INSERT INTO failover_conditions (provider_id, condition_type, threshold_value, updated_at)
            VALUES (?, ?, ?, datetime('now'))""",
            (provider_id, condition_type, threshold_value),
        )


def failover_conditions_delete_for_provider(provider_id: str) -> None:
    with _get_conn() as c:
        c.execute("DELETE FROM failover_conditions WHERE provider_id = ?", (provider_id,))


def failover_conditions_replace_all(conditions: list[tuple[str, str, Any]]) -> None:
    """Replace all failover conditions. Each item: (provider_id, condition_type, threshold_value)."""
    with _get_conn() as c:
        c.execute("DELETE FROM failover_conditions")
        for provider_id, condition_type, threshold_value in conditions:
            c.execute(
                """INSERT INTO failover_conditions (provider_id, condition_type, threshold_value, updated_at)
                VALUES (?, ?, ?, datetime('now'))""",
                (provider_id, condition_type, threshold_value),
            )


# --- model_aliases ---

def model_aliases_get_all() -> dict[str, str]:
    with _get_conn() as c:
        rows = c.execute("SELECT alias, canonical_id FROM model_aliases").fetchall()
        return {r["alias"]: r["canonical_id"] for r in rows}


def model_aliases_set(alias: str, canonical_id: str) -> None:
    with _get_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO model_aliases (alias, canonical_id) VALUES (?, ?)",
            (alias, canonical_id),
        )


def model_aliases_delete(alias: str) -> None:
    with _get_conn() as c:
        c.execute("DELETE FROM model_aliases WHERE alias = ?", (alias,))


def model_aliases_resolve(alias: str) -> Optional[str]:
    with _get_conn() as c:
        r = c.execute("SELECT canonical_id FROM model_aliases WHERE alias = ?", (alias,)).fetchone()
        return r["canonical_id"] if r else None


# --- agent_override ---

def agent_override_get(session_id: str) -> Optional[str]:
    with _get_conn() as c:
        r = c.execute("SELECT provider_id FROM agent_override WHERE session_id = ?", (session_id,)).fetchone()
        return r["provider_id"] if r and r["provider_id"] else None


def agent_override_set(session_id: str, provider_id: Optional[str]) -> None:
    with _get_conn() as c:
        if provider_id is None:
            c.execute("DELETE FROM agent_override WHERE session_id = ?", (session_id,))
        else:
            c.execute(
                """INSERT INTO agent_override (session_id, provider_id, created_at)
                VALUES (?, ?, datetime('now')) ON CONFLICT(session_id) DO UPDATE SET
                provider_id = excluded.provider_id, created_at = datetime('now')""",
                (session_id, provider_id),
            )
