"""
Abstract adapter interface. Plan 5.1.
Routing engine uses this; concrete adapters (and mocks) implement it.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class AdapterInterface(ABC):
    """Interface for calling a provider's chat/completions and embeddings."""

    @abstractmethod
    async def call_chat_completions(
        self,
        provider_id: str,
        endpoint: str,
        api_key_decrypted: str | None,
        model_upstream: str,
        body: dict[str, Any],
        stream: bool,
    ) -> tuple[dict[str, Any] | AsyncIterator[bytes], int, dict[str, str]]:
        """
        POST to provider chat/completions. Returns (response_body_or_stream, status_code, headers).
        If stream=True, first element is an async iterator of SSE bytes.
        """
        ...

    @abstractmethod
    async def call_embeddings(
        self,
        provider_id: str,
        endpoint: str,
        api_key_decrypted: str | None,
        model_upstream: str,
        body: dict[str, Any],
    ) -> tuple[dict[str, Any], int, dict[str, str]]:
        """POST to provider embeddings. Returns (response_body, status_code, headers)."""
        ...
