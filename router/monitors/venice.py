"""
Venice billing adapter: thin HTTP client, no Venice SDK.
Uses VENICE_BILLING_BASE_URL (default https://api.venice.ai/api/v1). Do not use provider inference endpoint for billing.
Endpoint order: (1) GET /billing/balance, (2) GET /billing/summary, (3) GET /billing/usage.
Raises on fetch/parse errors; credit loop catches and does not overwrite last-known-good.
"""

import os
from datetime import datetime
from typing import Any, Optional

import httpx

from router.monitors.schemas import CreditStatus

VENICE_BILLING_BASE_URL = os.environ.get("VENICE_BILLING_BASE_URL", "https://api.venice.ai/api/v1")
DEFAULT_TIMEOUT = 30.0


class VeniceMonitor:
    """Monitor for Venice providers. Uses billing API only; raises on errors."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client  # optional shared client from lifespan

    async def get_credit_status(self, provider: dict, now: datetime) -> CreditStatus:
        api_key: Optional[str] = provider.get("api_key") if isinstance(provider.get("api_key"), str) else None
        base = (VENICE_BILLING_BASE_URL or "").rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        # Prefer shared client from provider repr (injected by credit loop), then constructor
        use_client = provider.get("_http_client") or self._client

        # Try endpoints in order: balance (remaining), summary, usage
        balance_value: Optional[float] = None
        currency = "diem"

        async def _get(path: str) -> dict[str, Any]:
            url = f"{base}{path}"
            if use_client:
                r = await use_client.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            else:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as ac:
                    r = await ac.get(url, headers=headers)
            r.raise_for_status()
            return r.json()

        # 1) GET /billing/balance -> balances.diem
        try:
            data = await _get("/billing/balance")
            balances = data.get("balances") or data.get("balance") or {}
            if isinstance(balances, dict):
                balance_value = _float_or_none(balances.get("diem") or balances.get("balance"))
            elif isinstance(balances, (int, float)):
                balance_value = float(balances)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            # 2) Fallback: GET /billing/summary
            try:
                data = await _get("/billing/summary")
                balance_value = _float_or_none(
                    (data.get("remaining") or data.get("balance") or data.get("remaining_credit"))
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                # 3) Fallback: GET /billing/usage (may only have spend -> balance None)
                try:
                    data = await _get("/billing/usage")
                    balance_value = _float_or_none(
                        data.get("remaining") or data.get("balance") or data.get("remaining_credit")
                    )
                except (httpx.HTTPError, KeyError, TypeError, ValueError):
                    raise

        return CreditStatus(
            supported=True,
            balance=balance_value,
            currency=currency,
            below_threshold=None,
            as_of=now.isoformat(),
            raw=None,
        )


def _float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
