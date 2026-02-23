"""Run the router: python -m router (from repo root or with package installed)."""

if __name__ == "__main__":
    import uvicorn
    from router.config import load_config
    config = load_config()
    port = config["server"]["port"]
    bind_localhost = config["server"].get("admin_bind_localhost_only", True)
    host = "127.0.0.1" if bind_localhost else "0.0.0.0"
    uvicorn.run(
        "router.main:app",
        host=host,
        port=port,
        reload=False,
    )
