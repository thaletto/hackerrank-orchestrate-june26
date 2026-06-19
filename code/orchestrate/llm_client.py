"""Small LiteLLM wrapper used by the rest of the pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class LLMUnavailable(RuntimeError):
    """Raised when the configured LLM path cannot be used."""


@dataclass
class LLMResult:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LiteLLMClient:
    def __init__(
        self,
        model: str,
        fallback_model: str | None = None,
        temperature: float = 0,
        max_tokens: int = 900,
    ) -> None:
        self.model = model
        self.fallback_model = fallback_model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @staticmethod
    def _api_key_for_model(model: str) -> str | None:
        """Return an explicit API key for known providers."""
        if model.startswith("openrouter/"):
            return os.getenv("OPENROUTER_API_KEY")
        if model.startswith("groq/"):
            return os.getenv("GROQ_API_KEY")
        if model.startswith("gemini/") or model.startswith("vertex_ai/"):
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return os.getenv("OPENAI_API_KEY")

    @staticmethod
    def _api_base_for_model(model: str) -> str | None:
        """Return an explicit base URL for known providers."""
        if model.startswith("openrouter/"):
            return "https://openrouter.ai/api/v1"
        return None

    def complete(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, str] | None = {"type": "json_object"},
    ) -> LLMResult:
        try:
            from litellm import completion
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise LLMUnavailable(
                "LiteLLM is not installed. Install requirements or set HRO_USE_LLM=0."
            ) from exc

        errors: list[str] = []
        for model in [self.model, self.fallback_model]:
            if not model:
                continue
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format
                api_key = self._api_key_for_model(model)
                if api_key:
                    kwargs["api_key"] = api_key
                api_base = self._api_base_for_model(model)
                if api_base:
                    kwargs["api_base"] = api_base
                response = completion(**kwargs)
                choice = response["choices"][0]["message"]["content"]
                if choice is None:
                    raise LLMUnavailable(f"{model}: returned empty content (None)")
                usage = response.get("usage") or {}
                return LLMResult(
                    content=choice,
                    model=model,
                    input_tokens=int(usage.get("prompt_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or 0),
                )
            except LLMUnavailable:
                raise
            except Exception as exc:  # pragma: no cover - provider dependent
                errors.append(f"{model}: {exc}")
        raise LLMUnavailable("; ".join(errors) or "No configured model returned a result.")
