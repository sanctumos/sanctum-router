"""
Credit and health monitor. Plan 6 + Provider Monitor Adapters.
Phase 1: credit and health state in memory only; DB stores only provider settings and thresholds.
- Credit: normalized CreditStatus per provider; below_threshold only when supported + balance + credit_threshold all set.
- Monitors raise on errors; credit loop catches and does not overwrite last-known-good.
- Health: GET {endpoint}/models; 200→healthy, 401/403→unhealthy, 404/405→healthy, 429→unhealthy (http_429), 5xx→unhealthy.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx

# In-memory credit state: one structure per provider_id (balance, currency, below_threshold, as_of, error, supported, enforceable).
_credit_state: dict[str, dict[str, Any]] = {}
_health_healthy: dict[str, bool] = {}
_health_error: dict[str, Optional[str]] = {}  # e.g. "http_429"


def get_credit_balance(provider_id: str) -> Optional[float]:
    """Return current balance or None if unknown. Backward compat for routing_engine."""
    return (_credit_state.get(provider_id) or {}).get("balance")


def is_below_credit_threshold(provider_id: str) -> bool:
    """True only when below_threshold is True and state is enforceable (supported + non-None balance)."""
    s = _credit_state.get(provider_id) or {}
    return bool(s.get("enforceable") and s.get("below_threshold"))


def set_credit_state(
    provider_id: str,
    *,
    supported: bool,
    balance: Optional[float],
    currency: Optional[str],
    below_threshold: Optional[bool],
    as_of: str,
    error: Optional[str] = None,
    credit_threshold: Optional[float] = None,
) -> None:
    """
    Update in-memory credit state. Compute below_threshold only when
    supported and balance is not None and credit_threshold is not None (then balance < credit_threshold).
    """
    if credit_threshold is not None and supported and balance is not None:
        computed_below = balance < credit_threshold
    else:
        computed_below = below_threshold if below_threshold is not None else False
    enforceable = supported and balance is not None
    _credit_state[provider_id] = {
        "supported": supported,
        "balance": balance,
        "currency": currency or None,
        "below_threshold": computed_below,
        "as_of": as_of,
        "error": error,
        "enforceable": enforceable,
    }


def is_healthy(provider_id: str) -> bool:
    """Return current health (default True if never set)."""
    return _health_healthy.get(provider_id, True)


def set_healthy(provider_id: str, healthy: bool, error: Optional[str] = None) -> None:
    _health_healthy[provider_id] = healthy
    _health_error[provider_id] = error


def get_all_credit_state() -> dict[str, dict[str, Any]]:
    """For /admin/credit: supported, optional enforceable, balance, currency, below_threshold, as_of, optional error. Never raw."""
    return {
        pid: {
            "supported": s.get("supported", False),
            "enforceable": s.get("enforceable", False),
            "balance": s.get("balance"),
            "currency": s.get("currency"),
            "below_threshold": s.get("below_threshold", False),
            "as_of": s.get("as_of", ""),
            "error": s.get("error"),
        }
        for pid, s in _credit_state.items()
    }


def get_all_health() -> dict[str, bool]:
    return dict(_health_healthy)


def get_health_error(provider_id: str) -> Optional[str]:
    return _health_error.get(provider_id)


def register_credit_fetcher(provider_id: str, fetcher: Any) -> None:
    """Deprecated: no-op. Credit is now driven by monitor registry and run_credit_loop."""

def set_credit_state_legacy(provider_id: str, balance: Optional[float], below_threshold: bool) -> None:
    """Legacy helper: set state from (balance, below_threshold). Uses supported=True; credit_threshold=None so below_threshold is used as-is."""
    from datetime import datetime, timezone

    set_credit_state(
        provider_id=provider_id,
        supported=True,
        balance=balance,
        currency="USD",
        below_threshold=below_threshold,
        as_of=datetime.now(timezone.utc).isoformat(),
        error=None,
        credit_threshold=None,
    )


# Health: GET {endpoint}/models (endpoint is base including /v1). Defaults from config.monitoring.
HEALTH_CHECK_PATH = "/models"


async def _check_health(
    endpoint: str,
    api_key: Optional[str] = None,
    timeout: float = 10.0,
    client: Optional[httpx.AsyncClient] = None,
) -> tuple[bool, Optional[str]]:
    """
    GET {endpoint}/models. Return (healthy, error).
    200→healthy; 401/403→unhealthy; 404/405→healthy (endpoint reachable, health unsupported);
    429→unhealthy, error="http_429"; 5xx/timeout→unhealthy.
    """
    base = endpoint.rstrip("/")
    url = base + "/models" if base.endswith("v1") else base + "/v1/models"
    if not url.startswith("http"):
        return False, None
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        if client:
            r = await client.get(url, headers=headers or None, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout) as client_inner:
                r = await client_inner.get(url, headers=headers or None)
        if r.status_code == 200:
            return True, None
        if r.status_code in (401, 403):
            return False, None
        if r.status_code in (404, 405):
            return True, None  # endpoint reachable; health check unsupported
        if r.status_code == 429:
            return False, "http_429"
        if r.status_code >= 500:
            return False, None
        return False, None
    except (OSError, httpx.RequestError, httpx.TimeoutException):
        return False, None


async def run_health_check(
    provider_id: str,
    endpoint: str,
    api_key: Optional[str] = None,
    timeout: float = 10.0,
    client: Optional[httpx.AsyncClient] = None,
) -> None:
    """Run one health check and update in-memory state. Auth when api_key set."""
    healthy, error = await _check_health(endpoint, api_key=api_key, timeout=timeout, client=client)
    set_healthy(provider_id, healthy, error=error)


async def run_credit_loop(
    get_providers: Callable[[], list[dict[str, Any]]],
    interval_seconds: float = 300,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    """
    Background loop: every interval_seconds, for each provider resolve monitor by provider_type,
    call get_credit_status(provider, now). On exception: set error, do not overwrite last-known-good.
    get_providers returns list of dicts with id, endpoint, api_key, credit_threshold, provider_type.
    """
    from router.monitors import get_monitor

    fail_count: dict[str, int] = {}
    N_FAIL_BEFORE_OVERWRITE = 3  # keep last-known-good for N consecutive failures

    while True:
        try:
            providers = get_providers()
            now = datetime.now(timezone.utc)
            for prov in providers:
                pid = prov.get("id")
                if not pid:
                    continue
                provider_type = (prov.get("provider_type") or "").strip() or "openai_compat"
                credit_threshold = prov.get("credit_threshold")
                monitor = get_monitor(provider_type)
                provider_repr = {
                    "id": pid,
                    "endpoint": prov.get("endpoint"),
                    "api_key": prov.get("api_key"),
                    "credit_threshold": credit_threshold,
                    "provider_type": provider_type,
                }
                if http_client is not None:
                    provider_repr["_http_client"] = http_client
                try:
                    status = await monitor.get_credit_status(provider_repr, now)
                    fail_count[pid] = 0
                    set_credit_state(
                        provider_id=pid,
                        supported=status.supported,
                        balance=status.balance,
                        currency=status.currency,
                        below_threshold=status.below_threshold,
                        as_of=status.as_of,
                        error=None,
                        credit_threshold=credit_threshold,
                    )
                except Exception as e:
                    fail_count[pid] = fail_count.get(pid, 0) + 1
                    err_msg = "parse_error"
                    if isinstance(e, httpx.HTTPStatusError):
                        err_msg = f"http_{e.response.status_code}"
                    elif isinstance(e, (httpx.TimeoutException, asyncio.TimeoutError)):
                        err_msg = "timeout"
                    elif isinstance(e, (OSError, httpx.RequestError)):
                        err_msg = "request_error"
                    if fail_count[pid] < N_FAIL_BEFORE_OVERWRITE:
                        existing = _credit_state.get(pid)
                        if existing:
                            _credit_state[pid] = {**existing, "error": err_msg}
                        else:
                            set_credit_state(
                                provider_id=pid,
                                supported=True,
                                balance=None,
                                currency=None,
                                below_threshold=False,
                                as_of=now.isoformat(),
                                error=err_msg,
                                credit_threshold=credit_threshold,
                            )
                    else:
                        set_credit_state(
                            provider_id=pid,
                            supported=True,
                            balance=None,
                            currency=None,
                            below_threshold=False,
                            as_of=now.isoformat(),
                            error=err_msg,
                            credit_threshold=credit_threshold,
                        )
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError, KeyError):
            pass
        await asyncio.sleep(interval_seconds)


async def run_health_loop(
    get_provider_triples: Callable[[], list[tuple[str, str, Optional[str]]]],
    interval_seconds: float = 60,
    timeout: float = 10.0,
    client: Optional[httpx.AsyncClient] = None,
) -> None:
    """Background loop: (provider_id, endpoint, api_key) per provider; auth when api_key set."""
    while True:
        try:
            for provider_id, endpoint, api_key in get_provider_triples():
                await run_health_check(provider_id, endpoint, api_key=api_key, timeout=timeout, client=client)
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError):
            pass
        await asyncio.sleep(interval_seconds)
