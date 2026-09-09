"""Ollama provider adapter for ForgeAI's model router."""

from __future__ import annotations

from typing import Any

from forgeai.ai.ollama_client import OllamaClient


class OllamaProvider:
    """Adapt OllamaClient to the generic ModelProvider interface."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        base_url: str = "http://localhost:11434",
        num_ctx: int | None = None,
    ) -> None:
        self.client = client or OllamaClient()
        self.base_url = base_url
        self.num_ctx = num_ctx

    def generate(self, prompt: str, model: str, **kwargs: Any) -> str:
        """Generate a response through the configured local Ollama instance."""
        if "num_ctx" not in kwargs and self.num_ctx is not None:
            kwargs["num_ctx"] = self.num_ctx

        return self.client.generate(
            prompt=prompt,
            model=model,
            base_url=self.base_url,
            **kwargs,
        )
