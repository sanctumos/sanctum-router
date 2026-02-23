"""Provider adapters: abstract interface and OpenAI-compatible implementation."""

from router.adapters.base import AdapterInterface
from router.adapters.openai_compatible import OpenAICompatibleAdapter

__all__ = ["AdapterInterface", "OpenAICompatibleAdapter"]
