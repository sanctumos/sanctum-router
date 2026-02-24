"""Integration tests: FastAPI TestClient for /v1/* and /admin/*."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from router.main import create_app
from router import credit_health


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer test-admin-key"}


@pytest.fixture
def client_headers():
    return {"Authorization": "Bearer test-client-key"}


def test_health(client):
    """GET /health returns 200 and status ok when DB works."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert "db" not in data or data.get("db") in ("error", None)


def test_v1_models_empty(client, client_headers):
    """GET /v1/models returns list (empty when no providers)."""
    r = client.get("/v1/models", headers=client_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "list"
    assert "data" in data


def test_v1_requires_auth_when_keys_set(client):
    """GET /v1/models without auth returns 401 when ROUTER_CLIENT_KEY is set."""
    r = client.get("/v1/models")
    assert r.status_code == 401


def test_admin_status(client, admin_headers):
    """GET /admin/status returns version, current_provider, providers_healthy, uptime."""
    r = client.get("/admin/status", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "current_provider" in data
    assert "providers_healthy" in data
    assert "uptime_seconds" in data


def test_admin_create_provider_requires_encryption_key(client, admin_headers):
    """POST /admin/providers with api_key when encryption unavailable returns 400 (Issue #2)."""
    with patch("router.admin.encryption_available", return_value=False):
        r = client.post(
            "/admin/providers",
            headers=admin_headers,
            json={
                "id": "need-encryption",
                "endpoint": "https://api.example.com",
                "models": ["gpt-4"],
                "priority": 1,
                "api_key": "secret",
            },
        )
    assert r.status_code == 400
    assert "ROUTER_ENCRYPTION_KEY" in r.json().get("detail", "")


def test_admin_providers_crud(client, admin_headers):
    """POST /admin/providers, GET list, PATCH, DELETE."""
    r = client.post(
        "/admin/providers",
        headers=admin_headers,
        json={
            "id": "int-test-provider",
            "endpoint": "https://api.example.com",
            "models": ["gpt-4"],
            "priority": 1,
        },
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
    r2 = client.get("/admin/providers", headers=admin_headers)
    assert r2.status_code == 200
    ids = [p["id"] for p in r2.json()]
    assert "int-test-provider" in ids
    r3 = client.patch(
        "/admin/providers/int-test-provider",
        headers=admin_headers,
        json={"endpoint": "https://api.example.com/v1"},
    )
    assert r3.status_code == 200
    r4 = client.delete("/admin/providers/int-test-provider", headers=admin_headers)
    assert r4.status_code == 200
    assert r4.json().get("deleted") == "int-test-provider"


def test_admin_override(client, admin_headers):
    """POST /admin/override sets session override."""
    r = client.post(
        "/admin/override",
        headers=admin_headers,
        json={"provider_id": "some-provider"},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert r.json().get("current_provider") == "some-provider"


def test_admin_estimate_cost(client, admin_headers):
    """POST /admin/estimate-cost returns estimated_cost, currency, model, tokens."""
    r = client.post(
        "/admin/estimate-cost",
        headers=admin_headers,
        json={"model": "gpt-4", "prompt_tokens": 10, "completion_tokens": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert "estimated_cost" in data
    assert data["currency"] == "USD"
    assert data["model"] == "gpt-4"
    assert data["tokens"] == 15


def test_admin_estimate_cost_rejects_negative_tokens(client, admin_headers):
    """POST /admin/estimate-cost returns 400 when tokens are negative (Issue #14)."""
    r = client.post(
        "/admin/estimate-cost",
        headers=admin_headers,
        json={"prompt_tokens": -1, "completion_tokens": 0},
    )
    assert r.status_code == 400
    r2 = client.post(
        "/admin/estimate-cost",
        headers=admin_headers,
        json={"prompt_tokens": 0, "completion_tokens": -5},
    )
    assert r2.status_code == 400


def test_admin_credit(client, admin_headers):
    """GET /admin/credit returns dict of provider credit state."""
    r = client.get("/admin/credit", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_admin_routing_config_get_put(client, admin_headers):
    """GET and PUT /admin/routing-config."""
    r = client.get("/admin/routing-config", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "strategy" in data
    assert "provider_order" in data
    assert "failover" in data
    r2 = client.put(
        "/admin/routing-config",
        headers=admin_headers,
        json={"strategy": "priority", "cost_optimization": False},
    )
    assert r2.status_code == 200
    assert r2.json().get("ok") is True
    assert "routing_config" in r2.json()


def test_admin_requires_auth(client):
    """GET /admin/status without auth returns 401."""
    r = client.get("/admin/status")
    assert r.status_code == 401


def test_v1_chat_completions_no_provider(client, client_headers):
    """POST /v1/chat/completions with no providers returns 503 (or 502 if provider unreachable)."""
    r = client.post(
        "/v1/chat/completions",
        headers=client_headers,
        json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code in (502, 503)
    data = r.json()
    assert "error" in data
    # no_provider/failover_exhausted when no providers or all fail; http_502 when provider unreachable
    assert data["error"].get("code") in ("no_provider", "failover_exhausted", "http_502")


def test_v1_chat_completions_invalid_json(client, client_headers):
    """POST /v1/chat/completions with invalid body returns 400."""
    h = {**client_headers, "Content-Type": "application/json"}
    r = client.post("/v1/chat/completions", headers=h, data=b"not json")
    assert r.status_code == 400


def test_v1_embeddings_no_provider(client, client_headers):
    """POST /v1/embeddings with no providers returns 503 (or 502 if provider unreachable)."""
    r = client.post(
        "/v1/embeddings",
        headers=client_headers,
        json={"model": "text-embedding-3-small", "input": "hello"},
    )
    assert r.status_code in (502, 503)


def test_v1_chat_completions_success_with_mocked_adapter(client, client_headers, admin_headers):
    """POST /v1/chat/completions returns 200 when provider exists and adapter returns success."""
    pid = "mock-provider-chat"
    # Ensure only our provider exists so routing picks it
    for p in client.get("/admin/providers", headers=admin_headers).json():
        client.delete(f"/admin/providers/{p['id']}", headers=admin_headers)
    client.post(
        "/admin/providers",
        headers=admin_headers,
        json={
            "id": pid,
            "endpoint": "https://mock.example.com",
            "models": ["gpt-4"],
            "priority": 1,
        },
    )
    credit_health.set_healthy(pid, True)
    credit_health.set_credit_state_legacy(pid, 100.0, False)
    async def fake_chat(provider_id, endpoint, api_key, model_upstream, body, stream):
        return ({"id": "gen-1", "choices": [{"message": {"content": "Hi"}}], "model": "gpt-4"}, 200, {})

    with patch("router.proxy._adapter") as m:
        m.call_chat_completions = AsyncMock(side_effect=fake_chat)
        r = client.post(
            "/v1/chat/completions",
            headers=client_headers,
            json={"model": f"{pid}+gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        assert r.json().get("id") == "gen-1"
        assert r.headers.get("X-Router-Provider") == pid


def test_v1_embeddings_success_with_mocked_adapter(client, client_headers, admin_headers):
    """POST /v1/embeddings returns 200 when provider exists and adapter returns success."""
    pid = "emb-provider-emb"
    for p in client.get("/admin/providers", headers=admin_headers).json():
        client.delete(f"/admin/providers/{p['id']}", headers=admin_headers)
    client.post(
        "/admin/providers",
        headers=admin_headers,
        json={
            "id": pid,
            "endpoint": "https://emb.example.com",
            "models": ["text-embedding-3-small"],
            "priority": 1,
        },
    )
    credit_health.set_healthy(pid, True)
    credit_health.set_credit_state_legacy(pid, 100.0, False)
    async def fake_emb(provider_id, endpoint, api_key, model_upstream, body):
        return ({"data": [{"embedding": [0.1]}], "model": "text-embedding-3-small"}, 200, {})

    with patch("router.proxy._adapter") as m:
        m.call_embeddings = AsyncMock(side_effect=fake_emb)
        r = client.post(
            "/v1/embeddings",
            headers=client_headers,
            json={"model": f"{pid}+text-embedding-3-small", "input": "hello"},
        )
        assert r.status_code == 200
        assert "data" in r.json()
        assert r.headers.get("X-Router-Provider") == pid


def test_v1_chat_completions_streaming_success(client, client_headers, admin_headers):
    """POST /v1/chat/completions with stream=True returns 200 and streaming body (Issue #1 fix)."""
    pid = "stream-provider-stream"
    for p in client.get("/admin/providers", headers=admin_headers).json():
        client.delete(f"/admin/providers/{p['id']}", headers=admin_headers)
    client.post(
        "/admin/providers",
        headers=admin_headers,
        json={
            "id": pid,
            "endpoint": "https://stream.example.com",
            "models": ["gpt-4"],
            "priority": 1,
        },
    )
    credit_health.set_healthy(pid, True)
    credit_health.set_credit_state_legacy(pid, 100.0, False)
    async def fake_chat_stream(provider_id, endpoint, api_key, model_upstream, body, stream):
        if not stream:
            return ({"choices": []}, 200, {})
        # Simulate adapter buffering then yielding (Issue #1 pattern)
        chunks = [b"data: ", b'{"choices":[{}]}\n\n', b"data: [DONE]\n\n"]
        async def gen():
            for c in chunks:
                yield c
        return (gen(), 200, {})

    with patch("router.proxy._adapter") as m:
        m.call_chat_completions = AsyncMock(side_effect=fake_chat_stream)
        r = client.post(
            "/v1/chat/completions",
            headers=client_headers,
            json={
                "model": f"{pid}+gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
        assert b"data: " in body
        assert b"data: [DONE]" in body
