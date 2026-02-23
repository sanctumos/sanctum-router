"""Unit tests for router.bootstrap."""
import os

import pytest

from router import db
from router import bootstrap


@pytest.fixture
def clean_db_path(tmp_path):
    path = str(tmp_path / "bootstrap.db")
    prev = os.environ.get("ROUTER_DB_PATH")
    os.environ["ROUTER_DB_PATH"] = path
    if os.path.isfile(path):
        os.remove(path)
    db.init_db(db_path=path)
    yield path
    if prev is None:
        os.environ.pop("ROUTER_DB_PATH", None)
    else:
        os.environ["ROUTER_DB_PATH"] = prev


def test_bootstrap_skipped_when_providers_exist(clean_db_path):
    """bootstrap_from_config returns False when DB already has providers."""
    db.provider_insert("existing", "https://a.com", None, "[]", 1)
    config = {"providers": {"new": {"endpoint": "https://b.com", "models": []}}}
    assert bootstrap.bootstrap_from_config(config) is False
    assert db.provider_count() == 1


def test_bootstrap_skipped_when_no_providers_in_config(clean_db_path):
    """bootstrap_from_config returns False when config has no providers."""
    config = {"providers": {}}
    assert bootstrap.bootstrap_from_config(config) is False
    assert db.provider_count() == 0


def test_bootstrap_seeds_providers(clean_db_path):
    """bootstrap_from_config seeds providers and routing_config when DB empty."""
    config = {
        "providers": {
            "p1": {"endpoint": "https://p1.com", "models": ["m1"], "priority": 1},
        },
        "routing": {"strategy": "priority", "cost_optimization": True},
    }
    assert bootstrap.bootstrap_from_config(config) is True
    assert db.provider_count() == 1
    p = db.provider_get("p1")
    assert p["endpoint"] == "https://p1.com"
    r = db.routing_config_get()
    assert r["cost_optimization"] == 1
