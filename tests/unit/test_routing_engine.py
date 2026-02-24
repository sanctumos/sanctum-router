"""Unit tests for router.routing_engine."""
import json
from unittest.mock import patch

import pytest

from router import db
from router import credit_health as ch
from router import routing_engine as re


@pytest.fixture
def clean_db_path(tmp_path):
    path = str(tmp_path / "routing.db")
    import os
    prev = os.environ.get("ROUTER_DB_PATH")
    os.environ["ROUTER_DB_PATH"] = path
    db.init_db(db_path=path)
    yield path
    if prev is None:
        os.environ.pop("ROUTER_DB_PATH", None)
    else:
        os.environ["ROUTER_DB_PATH"] = prev


@pytest.fixture
def two_providers(clean_db_path):
    db.provider_insert("openai", "https://openai.com", None, '["gpt-4"]', 1, supports_tools=1, supports_streaming=1, supports_multimodal=0)
    db.provider_insert("local", "https://local.com", None, '["gpt-4","gpt-3.5"]', 2, supports_tools=0, supports_streaming=1, supports_multimodal=0)
    ch.set_healthy("openai", True)
    ch.set_healthy("local", True)
    ch.set_credit_state_legacy("openai", 100.0, False)
    ch.set_credit_state_legacy("local", 100.0, False)


def test_resolve_canonical_model_passthrough(clean_db_path):
    """resolve_canonical_model returns request_model when no alias."""
    assert re.resolve_canonical_model("gpt-4") == "gpt-4"
    assert re.resolve_canonical_model("openai+gpt-4") == "openai+gpt-4"


def test_resolve_canonical_model_alias(clean_db_path):
    """resolve_canonical_model resolves alias from DB."""
    db.model_aliases_set("gpt", "openai+gpt-4")
    assert re.resolve_canonical_model("gpt") == "openai+gpt-4"


def test_upstream_model_part():
    """upstream_model_part returns model part after + or full id."""
    assert re.upstream_model_part("openai+gpt-4") == "gpt-4"
    assert re.upstream_model_part("gpt-4") == "gpt-4"


def test_filter_by_capability():
    """filter_by_capability filters by supports_tools, supports_streaming, supports_multimodal."""
    providers = [
        {"id": "a", "supports_tools": True, "supports_streaming": True, "supports_multimodal": False},
        {"id": "b", "supports_tools": False, "supports_streaming": True, "supports_multimodal": False},
    ]
    out = re.filter_by_capability(providers, has_tools=True, stream=False, multimodal=False)
    assert len(out) == 1
    assert out[0]["id"] == "a"
    out2 = re.filter_by_capability(providers, has_tools=False, stream=True, multimodal=False)
    assert len(out2) == 2


def test_filter_available():
    """filter_available excludes unhealthy and below-credit."""
    ch.set_healthy("a", True)
    ch.set_healthy("b", False)
    ch.set_credit_state_legacy("a", 100.0, False)
    ch.set_credit_state_legacy("c", 1.0, True)
    providers = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    out = re.filter_available(providers)
    assert [p["id"] for p in out] == ["a"]


def test_resolve_candidates_no_providers(clean_db_path):
    """resolve_candidates returns empty when no providers have model."""
    db.provider_insert("p1", "e", None, '["other-model"]', 1)
    ch.set_healthy("p1", True)
    cands, chosen, canonical = re.resolve_candidates("s1", "gpt-4", {"model": "gpt-4"})
    assert cands == []
    assert chosen is None
    assert canonical == "gpt-4"


def test_resolve_candidates_with_providers(two_providers):
    """resolve_candidates returns ordered list and chosen provider."""
    cands, chosen, canonical = re.resolve_candidates("s1", "gpt-4", {"model": "gpt-4"})
    assert len(cands) >= 1
    assert chosen in [p["id"] for p in cands]
    assert canonical == "gpt-4"


def test_resolve_candidates_override_honored(two_providers):
    """When session has override and provider is available, that provider is chosen."""
    db.agent_override_set("session-x", "local")
    cands, chosen, canonical = re.resolve_candidates("session-x", "gpt-4", {"model": "gpt-4"})
    assert chosen == "local"


def test_resolve_candidates_override_not_available_fallback(two_providers):
    """When override provider is not in available list, fall through to normal order."""
    db.agent_override_set("session-y", "nonexistent")
    cands, chosen, canonical = re.resolve_candidates("session-y", "gpt-4", {"model": "gpt-4"})
    assert chosen is not None
    assert chosen != "nonexistent"


def test_mark_provider_unhealthy():
    """mark_provider_unhealthy sets healthy to False in memory."""
    ch.set_healthy("p99", True)
    re.mark_provider_unhealthy("p99")
    assert ch.is_healthy("p99") is False


def test_is_multimodal_request():
    """_is_multimodal_request detects image_url / input_image in messages."""
    body = {"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]}
    assert re._is_multimodal_request(body) is True
    body2 = {"messages": [{"role": "user", "content": "text"}]}
    assert re._is_multimodal_request(body2) is False
