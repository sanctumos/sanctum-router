"""Unit tests for router.credit_health async (run_health_check, _check_health)."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from router import credit_health as ch


@pytest.mark.asyncio
async def test_check_health_returns_true_on_2xx():
    """_check_health returns True when GET returns status < 500."""
    with patch("router.credit_health.httpx.AsyncClient") as ac:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(return_value=mock_resp)
        healthy, error = await ch._check_health("https://api.example.com/v1", timeout=1.0)
        assert healthy is True
        assert error is None


@pytest.mark.asyncio
async def test_check_health_returns_false_on_5xx():
    """_check_health returns False when GET returns 5xx."""
    with patch("router.credit_health.httpx.AsyncClient") as ac:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(return_value=mock_resp)
        healthy, error = await ch._check_health("https://api.example.com", timeout=1.0)
        assert healthy is False


@pytest.mark.asyncio
async def test_check_health_returns_false_on_exception():
    """_check_health returns False on request error (e.g. OSError or httpx.RequestError)."""
    with patch("router.credit_health.httpx.AsyncClient") as ac:
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(side_effect=httpx.RequestError("network error"))
        healthy, error = await ch._check_health("https://api.example.com", timeout=1.0)
        assert healthy is False


@pytest.mark.asyncio
async def test_run_health_check_updates_state():
    """run_health_check sets healthy state for provider."""
    with patch("router.credit_health._check_health", new_callable=AsyncMock, return_value=(True, None)):
        await ch.run_health_check("health-prov", "https://api.example.com")
        assert ch.is_healthy("health-prov") is True
    with patch("router.credit_health._check_health", new_callable=AsyncMock, return_value=(False, None)):
        await ch.run_health_check("health-prov2", "https://bad.example.com")
        assert ch.is_healthy("health-prov2") is False


@pytest.mark.asyncio
async def test_check_health_404_405_returns_healthy():
    """404/405 → healthy (endpoint reachable; health check unsupported)."""
    with patch("router.credit_health.httpx.AsyncClient") as ac:
        for code in (404, 405):
            mock_resp = MagicMock()
            mock_resp.status_code = code
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            ac.return_value.__aexit__ = AsyncMock(return_value=None)
            inst = ac.return_value.__aenter__.return_value
            inst.get = AsyncMock(return_value=mock_resp)
            healthy, _ = await ch._check_health("https://api.example.com/v1", timeout=1.0)
            assert healthy is True


@pytest.mark.asyncio
async def test_check_health_429_returns_unhealthy_with_error():
    """429 → unhealthy, error=http_429."""
    with patch("router.credit_health.httpx.AsyncClient") as ac:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(return_value=mock_resp)
        healthy, error = await ch._check_health("https://api.example.com/v1", timeout=1.0)
        assert healthy is False
        assert error == "http_429"


@pytest.mark.asyncio
async def test_run_health_check_sends_authorization_when_api_key():
    """When api_key provided, request includes Authorization Bearer."""
    with patch("router.credit_health.httpx.AsyncClient") as ac:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(return_value=mock_resp)
        await ch.run_health_check("pid", "https://api.example.com/v1", api_key="sk-secret", timeout=1.0)
        call_kw = inst.get.call_args[1]
        assert call_kw.get("headers", {}).get("Authorization") == "Bearer sk-secret"
