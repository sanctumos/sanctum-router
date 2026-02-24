"""Unit tests for router.monitors: OpenAICompat, registry, Venice (mocked), credit loop, health semantics."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from router.monitors import get_monitor
from router.monitors.openai_compat import OpenAICompatMonitor
from router.monitors.schemas import CreditStatus


@pytest.mark.asyncio
async def test_openai_compat_returns_supported_false_no_http():
    """OpenAICompatMonitor returns supported=False, no HTTP call."""
    monitor = OpenAICompatMonitor()
    provider = {"id": "p1", "endpoint": "https://api.example.com", "api_key": None, "credit_threshold": None, "provider_type": "openai_compat"}
    now = datetime.now(timezone.utc)
    status = await monitor.get_credit_status(provider, now)
    assert status.supported is False
    assert status.balance is None
    assert status.currency is None
    assert status.below_threshold is None
    assert status.as_of == now.isoformat()
    assert isinstance(status, CreditStatus)


def test_registry_get_monitor_none_returns_openai_compat():
    """get_monitor(None) returns openai_compat monitor."""
    m = get_monitor(None)
    assert isinstance(m, OpenAICompatMonitor)


def test_registry_get_monitor_unknown_returns_openai_compat():
    """get_monitor('unknown') returns openai_compat monitor."""
    m = get_monitor("unknown")
    assert isinstance(m, OpenAICompatMonitor)


def test_registry_get_monitor_venice_returns_venice():
    """get_monitor('venice') returns Venice monitor."""
    from router.monitors.venice import VeniceMonitor
    m = get_monitor("venice")
    assert isinstance(m, VeniceMonitor)


@pytest.mark.asyncio
async def test_venice_raises_on_http_error():
    """VeniceMonitor raises on fetch error (credit loop catches)."""
    from router.monitors.venice import VeniceMonitor
    import httpx

    monitor = VeniceMonitor()
    provider = {"id": "v1", "api_key": "sk-test", "provider_type": "venice"}
    now = datetime.now(timezone.utc)

    with patch("router.monitors.venice.httpx.AsyncClient") as ac:
        ac.return_value.__aenter__ = AsyncMock(return_value=ac.return_value)
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        ac.return_value.get = AsyncMock(side_effect=httpx.HTTPStatusError("500", request=None, response=None))
        with pytest.raises(httpx.HTTPStatusError):
            await monitor.get_credit_status(provider, now)


@pytest.mark.asyncio
async def test_venice_fallback_summary_when_balance_fails():
    """When /billing/balance fails, VeniceMonitor falls back to /billing/summary and returns normalized CreditStatus."""
    from router.monitors.venice import VeniceMonitor
    from unittest.mock import MagicMock

    monitor = VeniceMonitor()
    provider = {"id": "v1", "api_key": "sk-test", "provider_type": "venice"}
    now = datetime.now(timezone.utc)

    async def mock_get(url, **kwargs):
        url_str = str(url)
        if "billing/balance" in url_str:
            raise Exception("balance endpoint failed")
        if "billing/summary" in url_str:
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(return_value={"remaining": 42.5})
            resp.raise_for_status = MagicMock()
            return resp
        raise Exception("unexpected path: %s" % url_str)

    with patch("router.monitors.venice.httpx.AsyncClient") as ac:
        inst = MagicMock()
        inst.get = AsyncMock(side_effect=mock_get)
        ac.return_value.__aenter__ = AsyncMock(return_value=inst)
        ac.return_value.__aexit__ = AsyncMock(return_value=None)
        status = await monitor.get_credit_status(provider, now)
    assert status.supported is True
    assert status.balance == 42.5
    assert status.currency == "diem"
    assert status.below_threshold is None
    assert status.as_of == now.isoformat()
