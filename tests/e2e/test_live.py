"""E2E tests: full app stack via TestClient (no separate server process)."""
import pytest
from fastapi.testclient import TestClient

from router.main import create_app


def test_health_via_test_client():
    """E2E-style: full app stack (lifespan, DB init) and GET /health via TestClient."""
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") in ("ok", "degraded")


def test_admin_and_proxy_mount_via_test_client():
    """E2E-style: app has /v1 and /admin mounted; auth works with test keys."""
    app = create_app()
    with TestClient(app) as client:
        r_health = client.get("/health")
        assert r_health.status_code == 200
        r_admin = client.get("/admin/status", headers={"Authorization": "Bearer test-admin-key"})
        assert r_admin.status_code == 200
        r_v1 = client.get("/v1/models", headers={"Authorization": "Bearer test-client-key"})
        assert r_v1.status_code == 200
