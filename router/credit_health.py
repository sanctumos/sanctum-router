"""
Credit and health monitor. Plan 6.
Phase 1: credit and health state in memory only; DB stores only provider settings and thresholds.
- get_credit_balance(provider_id) -> float | None
- Background loop: credit_check_interval, update state; mark below_threshold
- Health checks: periodic GET to provider endpoint; set unhealthy in memory; do not persist to DB
"""

import asyncio
from typing import Callable, Awaitable

import httpx

# In-memory state (no DB). Plan 6.2, 6.3. Single process, no locks needed.
_credit_balance: dict[str, float | None] = {}
_credit_below_threshold: dict[str, bool] = {}
_health_healthy: dict[str, bool] = {}


def get_credit_balance(provider_id: str) -> float | None:
    """Return current balance or None if unknown."""
    return _credit_balance.get(provider_id)


def is_below_credit_threshold(provider_id: str) -> bool:
    return _credit_below_threshold.get(provider_id, False)


def set_credit_state(provider_id: str, balance: float | None, below_threshold: bool) -> None:
    _credit_balance[provider_id] = balance
    _credit_below_threshold[provider_id] = below_threshold


def is_healthy(provider_id: str) -> bool:
    """Return current health (default True if never set)."""
    return _health_healthy.get(provider_id, True)


def set_healthy(provider_id: str, healthy: bool) -> None:
    _health_healthy[provider_id] = healthy


def get_all_credit_state() -> dict[str, dict]:
    """For /admin/credit: balance, currency, below_threshold per provider."""
    return {
        pid: {
            "balance": _credit_balance.get(pid),
            "below_threshold": _credit_below_threshold.get(pid, False),
            "currency": "USD",
        }
        for pid in set(_credit_balance) | set(_credit_below_threshold)
    }


def get_all_health() -> dict[str, bool]:
    return dict(_health_healthy)


# Optional: credit fetcher per provider type (Venice, Featherless, etc.). Returns None if no API.
CreditFetcher = Callable[[str], Awaitable[float | None]]

_credit_fetchers: dict[str, CreditFetcher] = {}


def register_credit_fetcher(provider_id: str, fetcher: CreditFetcher) -> None:
    _credit_fetchers[provider_id] = fetcher


async def _check_health(endpoint: str, timeout: float = 10.0) -> bool:
    """GET provider endpoint (e.g. /v1/models)."""
    base = endpoint.rstrip("/")
    url = base + "/models" if base.endswith("v1") else base + "/v1/models"
    if not url.startswith("http"):
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return r.status_code < 500
    except Exception:
        return False


async def run_health_check(provider_id: str, endpoint: str) -> None:
    """Run one health check and update in-memory state."""
    ok = await _check_health(endpoint)
    set_healthy(provider_id, ok)


async def run_credit_loop(
    get_providers: Callable[[], list[tuple[str, float | None]]],
    interval_seconds: float = 300,
) -> None:
    """
    Background loop: every interval_seconds, for each provider get balance (via fetcher or None),
    compare to threshold from get_providers (provider_id, credit_threshold), update in-memory state.
    """
    while True:
        try:
            providers = get_providers()
            for provider_id, credit_threshold in providers:
                balance = None
                fetcher = _credit_fetchers.get(provider_id)
                if fetcher:
                    try:
                        balance = await fetcher(provider_id)
                    except Exception:
                        pass
                below = credit_threshold is not None and balance is not None and balance < credit_threshold
                set_credit_state(provider_id, balance, below)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


async def run_health_loop(
    get_provider_endpoints: Callable[[], list[tuple[str, str]]],
    interval_seconds: float = 60,
) -> None:
    """Background loop: every interval_seconds, GET each provider endpoint and set healthy/unhealthy."""
    while True:
        try:
            for provider_id, endpoint in get_provider_endpoints():
                await run_health_check(provider_id, endpoint)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
