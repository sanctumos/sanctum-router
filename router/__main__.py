"""Run the router: python -m router (from repo root or with package installed)."""

if __name__ == "__main__":
    import uvicorn
    from router.config import load_config, get_server_params
    config = load_config()
    host, port = get_server_params(config)
    uvicorn.run(
        "router.main:app",
        host=host,
        port=port,
        reload=False,
    )
