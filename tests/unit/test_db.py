"""Unit tests for router.db."""
import json
import os

import pytest

from router import db


@pytest.fixture
def clean_db_path(tmp_path):
    """Use a fresh DB in tmp_path for each test."""
    path = str(tmp_path / "db.sqlite")
    prev = os.environ.get("ROUTER_DB_PATH")
    os.environ["ROUTER_DB_PATH"] = path
    db.init_db(db_path=path)
    yield path
    if prev is None:
        os.environ.pop("ROUTER_DB_PATH", None)
    else:
        os.environ["ROUTER_DB_PATH"] = prev


def test_init_db_idempotent(clean_db_path):
    """init_db can be called twice without error."""
    db.init_db(db_path=clean_db_path)
    assert db.provider_count() == 0


def test_provider_insert_and_list(clean_db_path):
    """provider_insert and provider_list."""
    db.provider_insert(
        id="test1",
        endpoint="https://api.example.com",
        api_key_encrypted=b"enc",
        models='["gpt-4"]',
        priority=1,
    )
    rows = db.provider_list()
    assert len(rows) == 1
    assert rows[0]["id"] == "test1"
    assert rows[0]["endpoint"] == "https://api.example.com"
    assert rows[0]["priority"] == 1


def test_provider_get(clean_db_path):
    """provider_get returns provider or None."""
    assert db.provider_get("missing") is None
    db.provider_insert("p1", "https://a.com", None, "[]", 1)
    p = db.provider_get("p1")
    assert p["id"] == "p1"
    assert p["endpoint"] == "https://a.com"


def test_provider_update(clean_db_path):
    """provider_update updates only given fields."""
    db.provider_insert("p1", "https://old.com", None, "[]", 1)
    db.provider_update("p1", endpoint="https://new.com", priority=2)
    p = db.provider_get("p1")
    assert p["endpoint"] == "https://new.com"
    assert p["priority"] == 2


def test_provider_delete(clean_db_path):
    """provider_delete removes provider and cascades."""
    db.provider_insert("p1", "https://a.com", None, "[]", 1)
    db.provider_priority_set("p1", 1)
    db.provider_delete("p1")
    assert db.provider_get("p1") is None
    assert db.provider_priority_get_all() == []


def test_provider_count(clean_db_path):
    """provider_count."""
    assert db.provider_count() == 0
    db.provider_insert("a", "e", None, "[]", 1)
    db.provider_insert("b", "e", None, "[]", 1)
    assert db.provider_count() == 2


def test_routing_config_get_set(clean_db_path):
    """routing_config_get and routing_config_set."""
    r = db.routing_config_get()
    assert r["strategy"] == "priority"
    db.routing_config_set(strategy="priority", cost_optimization=1)
    r2 = db.routing_config_get()
    assert r2["cost_optimization"] == 1


def test_provider_priority(clean_db_path):
    """provider_priority_set and provider_priority_get_all."""
    db.provider_insert("a", "e", None, "[]", 1)
    db.provider_insert("b", "e", None, "[]", 1)
    db.provider_priority_set("a", 10)
    db.provider_priority_set("b", 5)
    order = db.provider_priority_get_all()
    assert order == [("b", 5), ("a", 10)]  # sorted by priority_order


def test_model_aliases(clean_db_path):
    """model_aliases_set, get_all, resolve, delete."""
    db.model_aliases_set("gpt", "openai+gpt-4")
    assert db.model_aliases_resolve("gpt") == "openai+gpt-4"
    all_ = db.model_aliases_get_all()
    assert all_["gpt"] == "openai+gpt-4"
    db.model_aliases_delete("gpt")
    assert db.model_aliases_resolve("gpt") is None


def test_agent_override(clean_db_path):
    """agent_override_set and agent_override_get."""
    assert db.agent_override_get("s1") is None
    db.agent_override_set("s1", "provider-a")
    assert db.agent_override_get("s1") == "provider-a"
    db.agent_override_set("s1", None)
    assert db.agent_override_get("s1") is None


def test_failover_conditions(clean_db_path):
    """failover_conditions_replace_all and get_all."""
    db.provider_insert("p1", "e", None, "[]", 1)
    db.failover_conditions_replace_all([("p1", "credit", 0.5)])
    rows = db.failover_conditions_get_all()
    assert len(rows) == 1
    assert rows[0]["provider_id"] == "p1"
    assert rows[0]["condition_type"] == "credit"
