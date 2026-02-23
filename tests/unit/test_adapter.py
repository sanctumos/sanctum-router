"""Unit tests for router.adapters.openai_compatible."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from router.adapters import openai_compatible as adapter


def test_normalize_error_dict_message():
    """_normalize_error extracts message from error dict."""
    body = {"error": {"message": "Rate limited", "code": "rate_limit"}}
    out = adapter._normalize_error(429, body)
    assert out["error"]["message"] == "Rate limited"
    assert out["error"]["code"] == "http_429"


def test_normalize_error_error_string():
    """_normalize_error when error is string."""
    out = adapter._normalize_error(500, {"error": "Internal"})
    assert out["error"]["message"] == "Internal"


def test_normalize_error_plain_string():
    """_normalize_error when body is string."""
    out = adapter._normalize_error(502, "Bad Gateway")
    assert out["error"]["message"] == "Bad Gateway"


def test_ensure_trailing_slash():
    """_ensure_trailing_slash adds or keeps trailing slash."""
    assert adapter._ensure_trailing_slash("https://api.com") == "https://api.com/"
    assert adapter._ensure_trailing_slash("https://api.com/") == "https://api.com/"


@pytest.mark.asyncio
async def test_call_chat_completions_non_stream_success():
    """call_chat_completions returns JSON and 200 when provider returns 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {"id": "gen-1", "choices": []}
    mock_resp.text = ""

    with patch("router.adapters.openai_compatible.httpx.AsyncClient") as ac:
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=mock_resp)))
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.post = AsyncMock(return_value=mock_resp)

        a = adapter.OpenAICompatibleAdapter()
        body, status, headers = await a.call_chat_completions(
            "p1", "https://api.com", "key", "gpt-4", {"messages": []}, stream=False
        )
        assert status == 200
        assert body["id"] == "gen-1"
        assert "choices" in body


@pytest.mark.asyncio
async def test_call_chat_completions_4xx():
    """call_chat_completions returns normalized error on 4xx."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {}
    mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}

    with patch("router.adapters.openai_compatible.httpx.AsyncClient") as ac:
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.post = AsyncMock(return_value=mock_resp)

        a = adapter.OpenAICompatibleAdapter()
        body, status, headers = await a.call_chat_completions(
            "p1", "https://api.com", "key", "gpt-4", {"messages": []}, stream=False
        )
        assert status == 401
        assert body["error"]["message"] == "Invalid API key"
        assert body["error"]["code"] == "http_401"


@pytest.mark.asyncio
async def test_call_embeddings_success():
    """call_embeddings returns data and 200 on success."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {"data": [{"embedding": [0.1]}]}

    with patch("router.adapters.openai_compatible.httpx.AsyncClient") as ac:
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.post = AsyncMock(return_value=mock_resp)

        a = adapter.OpenAICompatibleAdapter()
        body, status, headers = await a.call_embeddings(
            "p1", "https://api.com", "key", "text-embedding-3", {"input": "hi"}
        )
        assert status == 200
        assert "data" in body
        assert len(body["data"]) == 1


@pytest.mark.asyncio
async def test_call_embeddings_timeout():
    """call_embeddings returns 504 on TimeoutException."""
    with patch("router.adapters.openai_compatible.httpx.AsyncClient") as ac:
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        a = adapter.OpenAICompatibleAdapter()
        body, status, headers = await a.call_embeddings(
            "p1", "https://api.com", None, "model", {}
        )
        assert status == 504
        assert "timeout" in body["error"]["message"].lower() or body["error"]["code"] == "http_504"
