from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wowlogs_agent.domain.ports.llm_client import LLMMessage
from wowlogs_agent.gateways.llm.anthropic_llm_client import AnthropicLLMClient


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Usage:
    input_tokens: int
    output_tokens: int


class _FakeMessage:
    def __init__(self, texts: list[str], model: str, input_tokens: int, output_tokens: int) -> None:
        self.content = [_Block(t) for t in texts]
        self.model = model
        self.usage = _Usage(input_tokens, output_tokens)

    def model_dump(self) -> dict[str, object]:
        return {"model": self.model, "content": [getattr(b, "text", None) for b in self.content]}


class _FakeMessages:
    def __init__(self, response: _FakeMessage) -> None:
        self._response = response
        self.last_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.last_kwargs = kwargs
        return self._response


class _FakeAnthropic:
    def __init__(self, response: _FakeMessage) -> None:
        self.messages = _FakeMessages(response)


def _client(response: _FakeMessage) -> tuple[AnthropicLLMClient, _FakeAnthropic]:
    fake = _FakeAnthropic(response)
    return AnthropicLLMClient(api_key="unused", client=fake), fake  # type: ignore[arg-type]


def test_splits_system_messages_and_passes_chat_messages() -> None:
    response = _FakeMessage(["ok"], model="claude-sonnet-4-6", input_tokens=10, output_tokens=3)
    client, fake = _client(response)

    client.complete(
        [
            LLMMessage(role="system", content="You are a coach."),
            LLMMessage(role="system", content="Be terse."),
            LLMMessage(role="user", content="Hello"),
            LLMMessage(role="assistant", content="Hi"),
            LLMMessage(role="user", content="Tips?"),
        ],
        model="claude-sonnet-4-6",
    )

    kwargs = fake.messages.last_kwargs
    assert kwargs is not None
    assert kwargs["system"] == "You are a coach.\n\nBe terse."
    assert kwargs["messages"] == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Tips?"},
    ]
    assert kwargs["model"] == "claude-sonnet-4-6"


def test_forwards_model_and_generation_parameters() -> None:
    response = _FakeMessage(["ok"], model="claude-opus-4-6", input_tokens=1, output_tokens=1)
    client, fake = _client(response)

    client.complete(
        [LLMMessage(role="user", content="hi")],
        model="claude-opus-4-6",
        max_tokens=256,
        temperature=0.7,
    )

    kwargs = fake.messages.last_kwargs
    assert kwargs is not None
    assert kwargs["max_tokens"] == 256
    assert kwargs["temperature"] == 0.7


def test_maps_response_to_llm_response() -> None:
    response = _FakeMessage(
        ["part one ", "part two"],
        model="claude-sonnet-4-6",
        input_tokens=42,
        output_tokens=7,
    )
    client, _ = _client(response)

    result = client.complete([LLMMessage(role="user", content="hi")], model="claude-sonnet-4-6")

    assert result.text == "part one part two"
    assert result.model == "claude-sonnet-4-6"
    assert result.input_tokens == 42
    assert result.output_tokens == 7
    assert result.raw["model"] == "claude-sonnet-4-6"


def test_empty_system_when_no_system_messages() -> None:
    response = _FakeMessage(["ok"], model="m", input_tokens=0, output_tokens=0)
    client, fake = _client(response)

    client.complete([LLMMessage(role="user", content="hi")], model="m")

    assert fake.messages.last_kwargs is not None
    assert fake.messages.last_kwargs["system"] == ""


def test_ignores_non_text_blocks_in_response() -> None:
    class _ToolBlock:
        type = "tool_use"
        # no `text` attribute

    response = _FakeMessage(["kept"], model="m", input_tokens=0, output_tokens=0)
    response.content = [_ToolBlock(), _Block("kept")]  # type: ignore[list-item]
    client, _ = _client(response)

    result = client.complete([LLMMessage(role="user", content="hi")], model="m")
    assert result.text == "kept"
