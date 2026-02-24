"""
Sanctum Router — single ASGI app.
Mounts /v1/* (proxy) and /admin/* (config). One process, one listener.
PRD §7 Architecture. Run with --workers 1 to avoid duplicate credit/health loops.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from fastapi import FastAPI

from router import __version__, db
from router.admin import router as admin_router
from router.bootstrap import bootstrap_from_config
from router.config import load_config, get_server_params
from router.credit_health import run_credit_loop, run_health_loop
from router.proxy import router as proxy_router

config = load_config()


def _get_providers_for_monitor_loops() -> list[dict[str, Any]]:
    """Return list of provider dicts with id, endpoint, api_key (decrypted), credit_threshold, provider_type for credit/health loops."""
    from router.crypto_utils import decrypt_api_key

    rows = db.provider_list()
    return [
        {
            "id": p["id"],
            "endpoint": p["endpoint"],
            "api_key": decrypt_api_key(p.get("api_key_encrypted")),
            "credit_threshold": p.get("credit_threshold"),
            "provider_type": p.get("provider_type") or "openai_compat",
        }
        for p in rows
    ]


def _get_health_triples() -> list[tuple[str, str, Optional[str]]]:
    """Return (provider_id, endpoint, api_key) for health loop. Auth when api_key set."""
    from router.crypto_utils import decrypt_api_key

    rows = db.provider_list()
    return [
        (p["id"], p["endpoint"], decrypt_api_key(p.get("api_key_encrypted")))
        for p in rows
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Init DB on startup; optional bootstrap; set start time; optional credit/health loops with shared httpx client."""
    import time
    from router.admin import set_start_time

    set_start_time(time.time())
    db.init_db()
    bootstrap_from_config(config)

    monitoring = config.get("monitoring") or {}
    credit_interval = float(monitoring.get("credit_check_interval", 300))
    health_interval = float(monitoring.get("health_check_interval", 60))
    health_timeout = float(monitoring.get("health_check_timeout", 10.0))

    shared_client: Optional[httpx.AsyncClient] = None
    credit_task = None
    health_task = None

    try:
        shared_client = httpx.AsyncClient(timeout=30.0)
        credit_task = asyncio.create_task(
            run_credit_loop(_get_providers_for_monitor_loops, interval_seconds=credit_interval, http_client=shared_client)
        )
        health_task = asyncio.create_task(
            run_health_loop(_get_health_triples, interval_seconds=health_interval, timeout=health_timeout, client=shared_client)
        )
    except Exception:
        pass

    yield

    if credit_task:
        credit_task.cancel()
        try:
            await credit_task
        except asyncio.CancelledError:
            pass
    if health_task:
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass
    if shared_client:
        await shared_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sanctum Router",
        description="OpenAI-compatible inference proxy with multi-provider routing",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(proxy_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health():
        """Healthcheck for Docker/orchestration; no auth. Returns 200 when app is up."""
        import sqlite3
        try:
            db.provider_count()
        except (sqlite3.Error, OSError):
            return {"status": "degraded", "db": "error"}
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    host, port = get_server_params(config)
    uvicorn.run(
        "router.main:app",
        host=host,
        port=port,
        reload=False,
    )
