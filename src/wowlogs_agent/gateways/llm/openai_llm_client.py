from __future__ import annotations

from collections.abc import Sequence

from wowlogs_agent.domain.ports.llm_client import LLMClient, LLMMessage, LLMResponse


class OpenAILLMClient(LLMClient):
    """Stub placeholder so the port shape stays honest across providers.

    Not wired into the container. Real implementation is deferred until a second
    provider is actually needed; keeping the class here documents the seam.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def complete(
        self,
        messages: Sequence[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        raise NotImplementedError("OpenAILLMClient is not implemented yet.")
