"""OpenAI-compatible providers: no credit API; always return supported=False."""

from datetime import datetime

from router.monitors.schemas import CreditStatus


class OpenAICompatMonitor:
    """Monitor for OpenAI-compatible providers. No HTTP; credit not supported."""

    async def get_credit_status(self, provider: dict, now: datetime) -> CreditStatus:
        return CreditStatus(
            supported=False,
            balance=None,
            currency=None,
            below_threshold=None,
            as_of=now.isoformat(),
            raw=None,
        )
