"""Run the router: python -m router (from repo root or with package installed)."""

from router.config import load_config

if __name__ == "__main__":
    import uvicorn
    config = load_config()
    port = config["server"]["port"]
    uvicorn.run(
        "router.main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
    )
