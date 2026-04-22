from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from wowlogs_agent.gateways.warcraft_logs.oauth_token_provider import OAuthTokenProvider
from wowlogs_agent.infrastructure.cache.filesystem_response_cache import FilesystemResponseCache


class WarcraftLogsGraphQLError(RuntimeError):
    """Non-2xx response or GraphQL `errors` field from WarcraftLogs."""


# Status codes worth retrying: 429 (rate limit) and 5xx (server-side transient).
# Everything else — 4xx auth/schema/validation — is permanent.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class WarcraftLogsGraphQLClient:
    """Thin GraphQL transport with on-disk response caching keyed by (report, query, vars).

    Cache hits bypass the HTTP call entirely; only cache misses are subject to
    the retry/backoff policy, so replays never consume rate-limit budget.
    """

    def __init__(
        self,
        endpoint: str,
        token_provider: OAuthTokenProvider,
        cache: FilesystemResponseCache,
        http_client: httpx.Client | None = None,
        *,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._endpoint = endpoint
        self._token_provider = token_provider
        self._cache = cache
        self._http = http_client or httpx.Client(timeout=30.0)
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds
        self._sleep = sleep

    def execute(
        self,
        query: str,
        variables: Mapping[str, Any],
        *,
        cache_namespace: str,
    ) -> Mapping[str, Any]:
        key = self._cache_key(query, variables)
        cached = self._cache.get(cache_namespace, key)
        if cached is not None:
            return cached

        payload = self._post_with_retries(query, variables)
        self._cache.put(cache_namespace, key, payload)
        return payload

    def _post_with_retries(
        self,
        query: str,
        variables: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Exponential backoff around the POST. 429 honors Retry-After.

        Retries cover transient failures only: network errors and 429/5xx
        responses. 4xx (auth, bad query) raises immediately — retrying a
        permanent error just wastes the rate-limit budget we're trying to
        protect.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._post(query, variables)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == self._max_retries:
                    break
                self._sleep(self._backoff_base * (2**attempt))
                continue

            if response.status_code == 200:
                parsed: Mapping[str, Any] = response.json()
                if parsed.get("errors"):
                    raise WarcraftLogsGraphQLError(
                        f"WCL GraphQL errors: {parsed['errors']}"
                    )
                return parsed

            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                delay = retry_after if retry_after is not None else self._backoff_base * (2**attempt)
                self._sleep(delay)
                continue

            raise WarcraftLogsGraphQLError(
                f"WCL GraphQL returned {response.status_code}: {response.text[:200]}"
            )

        raise WarcraftLogsGraphQLError(
            f"WCL GraphQL request failed after {self._max_retries + 1} attempts: {last_error}"
        )

    def _post(self, query: str, variables: Mapping[str, Any]) -> httpx.Response:
        token = self._token_provider.get_token()
        return self._http.post(
            self._endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": dict(variables)},
        )

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        """Retry-After may be seconds (int) or an HTTP date. Only the seconds
        form is worth supporting here — WCL uses it, and HTTP-date handling
        would add a date-parsing dependency for no real gain."""
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @staticmethod
    def _cache_key(query: str, variables: Mapping[str, Any]) -> str:
        digest = hashlib.sha256()
        digest.update(query.encode("utf-8"))
        digest.update(b"\n--vars--\n")
        digest.update(json.dumps(variables, sort_keys=True).encode("utf-8"))
        return digest.hexdigest()[:32]
