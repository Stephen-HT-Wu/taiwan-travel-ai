import os

from providers.anthropic import AnthropicProvider
from providers.base import LLMProvider
from providers.gemini import GeminiProvider


def get_llm_provider() -> LLMProvider:
    provider = (os.getenv("LLM_PROVIDER") or "anthropic").lower()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "anthropic":
        return AnthropicProvider()
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")
