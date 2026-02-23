"""
Sanctum Router — single ASGI app.
Mounts /v1/* (proxy) and /admin/* (config). One process, one listener.
PRD §7 Architecture.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from router import __version__, db
from router.admin import router as admin_router
from router.bootstrap import bootstrap_from_config
from router.config import load_config
from router.proxy import router as proxy_router

config = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Init DB on startup; optional bootstrap from config; set start time for uptime."""
    import time
    from router.admin import set_start_time
    set_start_time(time.time())
    db.init_db()
    bootstrap_from_config(config)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sanctum Router",
        description="OpenAI-compatible inference proxy with multi-provider routing",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(proxy_router)
    app.include_router(admin_router)
    return app


app = create_app()


@app.get("/health")
async def health():
    """Healthcheck for Docker/orchestration; no auth. Returns 200 when app is up."""
    try:
        db.provider_count()
    except Exception:
        return {"status": "degraded", "db": "error"}
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = config["server"]["port"]
    # Bind whole router to 127.0.0.1 by default (localhost-only). PRD §7, plan 1.5.
    uvicorn.run(
        "router.main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
    )
