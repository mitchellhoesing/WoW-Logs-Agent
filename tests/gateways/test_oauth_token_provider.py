from __future__ import annotations

from typing import Any

import httpx
import pytest

from wowlogs_agent.gateways.warcraft_logs.oauth_token_provider import (
    OAuthError,
    OAuthTokenProvider,
)


class _FakeClient:
    """httpx.Client stand-in that returns scripted responses and records calls."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No more scripted responses")
        return self._responses.pop(0)


def _ok(token: str = "tok", expires_in: int = 3600) -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": token, "expires_in": expires_in, "token_type": "Bearer"},
    )


def _provider(client: _FakeClient) -> OAuthTokenProvider:
    return OAuthTokenProvider(
        client_id="cid",
        client_secret="secret",
        token_url="https://wcl.example/oauth/token",
        http_client=client,  # type: ignore[arg-type]
    )


def test_fetches_token_with_client_credentials_and_basic_auth() -> None:
    client = _FakeClient([_ok("abc123")])
    provider = _provider(client)

    assert provider.get_token() == "abc123"
    call = client.calls[0]
    assert call["url"] == "https://wcl.example/oauth/token"
    assert call["data"] == {"grant_type": "client_credentials"}
    assert call["auth"] == ("cid", "secret")


def test_caches_token_across_calls() -> None:
    client = _FakeClient([_ok("abc123", expires_in=3600)])
    provider = _provider(client)

    assert provider.get_token() == "abc123"
    assert provider.get_token() == "abc123"
    assert len(client.calls) == 1


def test_refreshes_when_cached_token_is_near_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient([_ok("first", expires_in=30), _ok("second", expires_in=3600)])
    provider = _provider(client)

    # Freeze "now" so the 60s safety margin always triggers on the 30s token.
    monkeypatch.setattr(
        "wowlogs_agent.gateways.warcraft_logs.oauth_token_provider.time.time",
        lambda: 1000.0,
    )
    assert provider.get_token() == "first"
    assert provider.get_token() == "second"
    assert len(client.calls) == 2


def test_raises_on_non_200_response() -> None:
    client = _FakeClient([httpx.Response(401, text="unauthorized")])
    provider = _provider(client)

    with pytest.raises(OAuthError, match="401"):
        provider.get_token()


def test_raises_when_access_token_missing() -> None:
    client = _FakeClient([httpx.Response(200, json={"expires_in": 3600})])
    provider = _provider(client)

    with pytest.raises(OAuthError, match="access_token"):
        provider.get_token()


def test_raises_when_expires_in_missing_or_invalid() -> None:
    client = _FakeClient([httpx.Response(200, json={"access_token": "t", "expires_in": 0})])
    provider = _provider(client)

    with pytest.raises(OAuthError, match="expires_in"):
        provider.get_token()
