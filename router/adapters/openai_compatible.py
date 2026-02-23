"""
Generic OpenAI-compatible adapter. Plan 5.2–5.4.
POST to {endpoint}/chat/completions and {endpoint}/embeddings; rewrite model; forward Authorization.
Stream SSE; timeouts (default 60s); normalize errors to OpenAI shape.
"""

import json
from typing import Any, AsyncIterator

import httpx

from router.adapters.base import AdapterInterface

# Default timeout per request. Plan 5.4.
DEFAULT_TIMEOUT = 60.0


def _normalize_error(status: int, body: Any) -> dict:
    """Return OpenAI-style error body."""
    msg = "Provider error"
    if isinstance(body, dict) and "error" in body:
        err = body["error"]
        if isinstance(err, dict) and "message" in err:
            msg = err["message"]
        elif isinstance(err, str):
            msg = err
    elif isinstance(body, str):
        msg = body[:500]
    return {"error": {"message": msg, "type": "api_error", "code": f"http_{status}"}}


def _ensure_trailing_slash(url: str) -> str:
    return url.rstrip("/") + "/" if url else "/"


class OpenAICompatibleAdapter(AdapterInterface):
    """Single generic adapter for any OpenAI-compatible HTTP API."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def _headers(self, api_key: str | None) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    async def call_chat_completions(
        self,
        provider_id: str,
        endpoint: str,
        api_key_decrypted: str | None,
        model_upstream: str,
        body: dict[str, Any],
        stream: bool,
    ) -> tuple[dict[str, Any] | AsyncIterator[bytes], int, dict[str, str]]:
        url = _ensure_trailing_slash(endpoint) + "chat/completions"
        payload = {**body, "model": model_upstream}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if stream:
                    async with client.stream(
                        "POST", url, json=payload, headers=self._headers(api_key_decrypted)
                    ) as resp:
                        status = resp.status_code
                        out_headers = dict(resp.headers)
                        if status >= 400:
                            body_bytes = await resp.aread()
                            try:
                                err_body = json.loads(body_bytes)
                            except Exception:
                                err_body = body_bytes.decode("utf-8", errors="replace")
                            return _normalize_error(status, err_body), status, out_headers
                        # Consume stream while response is still open to avoid closing before
                        # proxy consumes it (Issue #1). Buffer chunks then yield from buffer.
                        chunks: list[bytes] = []
                        async for chunk in resp.aiter_bytes():
                            chunks.append(chunk)

                        async def iter_chunks() -> AsyncIterator[bytes]:
                            for c in chunks:
                                yield c
                        return iter_chunks(), status, out_headers
                else:
                    resp = await client.post(
                        url, json=payload, headers=self._headers(api_key_decrypted)
                    )
                    status = resp.status_code
                    out_headers = dict(resp.headers)
                    try:
                        data = resp.json()
                    except Exception:
                        data = resp.text or ""
                    if status >= 400:
                        return _normalize_error(status, data), status, out_headers
                    return data, status, out_headers
        except httpx.TimeoutException:
            return _normalize_error(504, "Provider timeout"), 504, {}
        except httpx.RequestError as e:
            return _normalize_error(502, str(e)), 502, {}

    async def call_embeddings(
        self,
        provider_id: str,
        endpoint: str,
        api_key_decrypted: str | None,
        model_upstream: str,
        body: dict[str, Any],
    ) -> tuple[dict[str, Any], int, dict[str, str]]:
        url = _ensure_trailing_slash(endpoint) + "embeddings"
        payload = {**body, "model": model_upstream}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    url, json=payload, headers=self._headers(api_key_decrypted)
                )
                status = resp.status_code
                out_headers = dict(resp.headers)
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text or ""
                if status >= 400:
                    return _normalize_error(status, data), status, out_headers
                return data, status, out_headers
        except httpx.TimeoutException:
            return _normalize_error(504, "Provider timeout"), 504, {}
        except httpx.RequestError as e:
            return _normalize_error(502, str(e)), 502, {}
