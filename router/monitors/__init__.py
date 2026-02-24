"""
Provider monitor adapters: credit (and optionally health) per provider_type.
Registry by provider_type; default openai_compat. Monitors raise on fetch/parse errors;
credit loop catches and does not overwrite last-known-good state.
"""

from datetime import datetime
from typing import Any, Optional, Protocol

from router.monitors.schemas import CreditStatus

# Minimal provider representation for monitor calls (id, endpoint, api_key Optional[str], credit_threshold, provider_type)
ProviderRepr = dict[str, Any]

PROVIDER_MONITORS: dict[str, "ProviderMonitor"] = {}


class ProviderMonitor(Protocol):
    """Protocol for per-provider credit (and optionally rate/health) adapters."""

    async def get_credit_status(self, provider: ProviderRepr, now: datetime) -> CreditStatus:
        ...


def get_monitor(provider_type: Optional[str]) -> "ProviderMonitor":
    """Return monitor for provider_type; default openai_compat."""
    key = (provider_type or "").strip() or "openai_compat"
    return PROVIDER_MONITORS.get(key) or PROVIDER_MONITORS["openai_compat"]


# Register built-in monitors (openai_compat first so get_monitor default exists)
def _register_monitors() -> None:
    from router.monitors.openai_compat import OpenAICompatMonitor
    from router.monitors.venice import VeniceMonitor

    PROVIDER_MONITORS["openai_compat"] = OpenAICompatMonitor()
    PROVIDER_MONITORS["venice"] = VeniceMonitor()


_register_monitors()

__all__ = [
    "CreditStatus",
    "ProviderMonitor",
    "ProviderRepr",
    "PROVIDER_MONITORS",
    "get_monitor",
]
