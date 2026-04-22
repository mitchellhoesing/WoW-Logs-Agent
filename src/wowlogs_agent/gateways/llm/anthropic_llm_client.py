from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from anthropic import Anthropic

from wowlogs_agent.domain.ports.llm_client import LLMClient, LLMMessage, LLMResponse


class AnthropicLLMClient(LLMClient):
    """Anthropic Messages API adapter.

    Splits `system` messages out (Anthropic takes `system` as a top-level parameter)
    and maps the remaining messages to the Messages API shape.
    """

    def __init__(self, api_key: str, client: Anthropic | None = None) -> None:
        self._client = client or Anthropic(api_key=api_key)

    def complete(
        self,
        messages: Sequence[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat_messages: list[dict[str, str]] = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        result = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system="\n\n".join(system_parts) if system_parts else "",
            messages=cast(Any, chat_messages),
        )

        text_parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                text_parts.append(text)

        return LLMResponse(
            text="".join(text_parts),
            model=result.model,
            input_tokens=int(getattr(result.usage, "input_tokens", 0)),
            output_tokens=int(getattr(result.usage, "output_tokens", 0)),
            raw=cast(dict[str, object], result.model_dump()),
        )
