"""Unit tests for proxy _models_from_db and GET /v1/models with providers."""
import json

import pytest
from fastapi.testclient import TestClient

from router import db
from router.main import create_app


@pytest.fixture
def app_with_provider(tmp_path):
    import os
    path = str(tmp_path / "models.db")
    prev = os.environ.get("ROUTER_DB_PATH")
    os.environ["ROUTER_DB_PATH"] = path
    db.init_db(db_path=path)
    db.provider_insert("openai", "https://api.openai.com", None, '["gpt-4","gpt-3.5"]', 1)
    db.model_aliases_set("gpt", "openai+gpt-4")
    app = create_app()
    yield app
    if prev is None:
        os.environ.pop("ROUTER_DB_PATH", None)
    else:
        os.environ["ROUTER_DB_PATH"] = prev


def test_get_models_with_providers_and_aliases(app_with_provider):
    """GET /v1/models returns provider+model ids and aliases."""
    with TestClient(app_with_provider) as client:
        r = client.get("/v1/models", headers={"Authorization": "Bearer test-client-key"})
        assert r.status_code == 200
        data = r.json()
        assert data["object"] == "list"
        ids = [m["id"] for m in data["data"]]
        assert "openai+gpt-4" in ids
        assert "openai+gpt-3.5" in ids
        assert "gpt" in ids
