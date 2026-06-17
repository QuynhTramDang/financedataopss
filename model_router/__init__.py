"""Model router package: task-aware LLM routing với structured-output + retry + fallback."""

from .providers import LLMResponse, LLMSchemaError, ProviderError, ProviderUnavailable
from .router import ModelRouter, get_router

__all__ = [
    "LLMResponse",
    "LLMSchemaError",
    "ProviderError",
    "ProviderUnavailable",
    "ModelRouter",
    "get_router",
]
