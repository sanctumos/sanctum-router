"""Shared types for provider monitors. Do not log or expose raw."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CreditStatus:
    """Normalized credit status from a monitor. raw must not be logged or returned in API."""

    supported: bool
    balance: Optional[float]
    currency: Optional[str]
    below_threshold: Optional[bool]
    as_of: str  # ISO datetime
    raw: Optional[dict] = None  # internal only; never log or expose
