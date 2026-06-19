"""Model health checks for the configured LiteLLM provider."""

from __future__ import annotations

from .config import PipelineConfig
from .llm_client import LLMUnavailable, LiteLLMClient


def haiku(config: PipelineConfig) -> str:
    """Ask the LLM for a haiku."""
    client = LiteLLMClient(
        model=config.model,
        fallback_model=config.fallback_model,
        temperature=0,
        max_tokens=120,
    )
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, tell me a haiku"},
    ]
    try:
        result = client.complete(messages, response_format=None)
        return result.content
    except LLMUnavailable:
        raise
