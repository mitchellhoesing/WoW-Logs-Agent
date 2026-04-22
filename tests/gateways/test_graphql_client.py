from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from wowlogs_agent.gateways.warcraft_logs.graphql_client import (
    WarcraftLogsGraphQLClient,
    WarcraftLogsGraphQLError,
)
from wowlogs_agent.infrastructure.cache.filesystem_response_cache import FilesystemResponseCache


class _FakeHTTP:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return self._responses.pop(0)


class _StaticTokenProvider:
    def __init__(self, token: str = "TOKEN") -> None:
        self.token = token
        self.calls = 0

    def get_token(self) -> str:
        self.calls += 1
        return self.token


def _client(
    http: _FakeHTTP,
    cache_root: Path,
    token_provider: Any | None = None,
    *,
    max_retries: int = 3,
    sleeps: list[float] | None = None,
) -> WarcraftLogsGraphQLClient:
    cache = FilesystemResponseCache(cache_root)
    recorded = sleeps if sleeps is not None else []
    return WarcraftLogsGraphQLClient(
        endpoint="https://wcl.example/graphql",
        token_provider=token_provider or _StaticTokenProvider(),  # type: ignore[arg-type]
        cache=cache,
        http_client=http,  # type: ignore[arg-type]
        max_retries=max_retries,
        backoff_base_seconds=0.01,
        sleep=recorded.append,
    )


def test_executes_query_and_sends_bearer_token(tmp_path: Path) -> None:
    http = _FakeHTTP([httpx.Response(200, json={"data": {"x": 1}})])
    tp = _StaticTokenProvider("abc")
    client = _client(http, tmp_path, tp)

    result = client.execute("{ x }", {"k": 1}, cache_namespace="ns")

    assert result == {"data": {"x": 1}}
    call = http.calls[0]
    assert call["url"] == "https://wcl.example/graphql"
    assert call["headers"]["Authorization"] == "Bearer abc"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"] == {"query": "{ x }", "variables": {"k": 1}}


def test_caches_response_and_skips_http_on_repeat(tmp_path: Path) -> None:
    http = _FakeHTTP([httpx.Response(200, json={"data": {"x": 1}})])
    tp = _StaticTokenProvider()
    client = _client(http, tmp_path, tp)

    first = client.execute("{ x }", {"k": 1}, cache_namespace="ns")
    second = client.execute("{ x }", {"k": 1}, cache_namespace="ns")

    assert first == second
    assert len(http.calls) == 1
    assert tp.calls == 1


def test_different_variables_produce_different_cache_keys(tmp_path: Path) -> None:
    http = _FakeHTTP(
        [
            httpx.Response(200, json={"data": {"x": 1}}),
            httpx.Response(200, json={"data": {"x": 2}}),
        ]
    )
    client = _client(http, tmp_path)

    a = client.execute("{ x }", {"k": 1}, cache_namespace="ns")
    b = client.execute("{ x }", {"k": 2}, cache_namespace="ns")

    assert a != b
    assert len(http.calls) == 2


def test_raises_on_non_retryable_status(tmp_path: Path) -> None:
    # 400 is treated as permanent — one response is all that's needed.
    http = _FakeHTTP([httpx.Response(400, text="bad request")])
    client = _client(http, tmp_path)

    with pytest.raises(WarcraftLogsGraphQLError, match="400"):
        client.execute("{ x }", {}, cache_namespace="ns")
    assert len(http.calls) == 1


def test_retries_5xx_then_succeeds(tmp_path: Path) -> None:
    http = _FakeHTTP(
        [
            httpx.Response(502, text="bad gateway"),
            httpx.Response(200, json={"data": {"x": 1}}),
        ]
    )
    sleeps: list[float] = []
    client = _client(http, tmp_path, sleeps=sleeps)

    result = client.execute("{ x }", {}, cache_namespace="ns")

    assert result == {"data": {"x": 1}}
    assert len(http.calls) == 2
    assert sleeps == [0.01]  # single exponential step before success


def test_retries_exhausted_raises(tmp_path: Path) -> None:
    http = _FakeHTTP([httpx.Response(503, text="busy")] * 4)
    client = _client(http, tmp_path, max_retries=3)

    with pytest.raises(WarcraftLogsGraphQLError, match="503"):
        client.execute("{ x }", {}, cache_namespace="ns")
    assert len(http.calls) == 4  # initial + 3 retries


def test_429_honors_retry_after_header(tmp_path: Path) -> None:
    http = _FakeHTTP(
        [
            httpx.Response(429, text="slow down", headers={"Retry-After": "7"}),
            httpx.Response(200, json={"data": {"x": 1}}),
        ]
    )
    sleeps: list[float] = []
    client = _client(http, tmp_path, sleeps=sleeps)

    result = client.execute("{ x }", {}, cache_namespace="ns")

    assert result == {"data": {"x": 1}}
    assert sleeps == [7.0]  # retry-after used in place of exponential backoff


def test_transport_error_retries(tmp_path: Path) -> None:
    class _FlakyHTTP:
        def __init__(self) -> None:
            self.calls = 0

        def post(self, url: str, **kwargs: Any) -> httpx.Response:
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectError("refused")
            return httpx.Response(200, json={"data": {"x": 1}})

    flaky = _FlakyHTTP()
    cache = FilesystemResponseCache(tmp_path)
    sleeps: list[float] = []
    client = WarcraftLogsGraphQLClient(
        endpoint="https://wcl.example/graphql",
        token_provider=_StaticTokenProvider(),  # type: ignore[arg-type]
        cache=cache,
        http_client=flaky,  # type: ignore[arg-type]
        backoff_base_seconds=0.01,
        sleep=sleeps.append,
    )

    result = client.execute("{ x }", {}, cache_namespace="ns")
    assert result == {"data": {"x": 1}}
    assert flaky.calls == 2


def test_raises_on_graphql_errors_field(tmp_path: Path) -> None:
    http = _FakeHTTP([httpx.Response(200, json={"errors": [{"message": "bad"}]})])
    client = _client(http, tmp_path)

    with pytest.raises(WarcraftLogsGraphQLError, match="bad"):
        client.execute("{ x }", {}, cache_namespace="ns")


def test_does_not_cache_error_responses(tmp_path: Path) -> None:
    http = _FakeHTTP(
        [
            httpx.Response(200, json={"errors": [{"message": "bad"}]}),
            httpx.Response(200, json={"data": {"x": 1}}),
        ]
    )
    client = _client(http, tmp_path)

    with pytest.raises(WarcraftLogsGraphQLError):
        client.execute("{ x }", {}, cache_namespace="ns")
    # Second call should hit HTTP again, not a cached error.
    assert client.execute("{ x }", {}, cache_namespace="ns") == {"data": {"x": 1}}
    assert len(http.calls) == 2
