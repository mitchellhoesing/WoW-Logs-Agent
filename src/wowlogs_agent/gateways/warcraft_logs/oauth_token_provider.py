from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import httpx


class OAuthError(RuntimeError):
    """Raised when WarcraftLogs OAuth token acquisition fails."""


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float


class OAuthTokenProvider:
    """Client-credentials OAuth2 flow for WarcraftLogs v2.

    Caches the access token in-memory until 60s before expiry. Thread-safe.
    """

    _SAFETY_MARGIN_SECONDS = 60.0

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._http = http_client or httpx.Client(timeout=15.0)
        self._lock = threading.Lock()
        self._cached: _CachedToken | None = None

    def get_token(self) -> str:
        with self._lock:
            now = time.time()
            if self._cached and self._cached.expires_at - self._SAFETY_MARGIN_SECONDS > now:
                return self._cached.access_token
            self._cached = self._fetch()
            return self._cached.access_token

    def _fetch(self) -> _CachedToken:
        response = self._http.post(
            self._token_url,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
        if response.status_code != 200:
            raise OAuthError(
                f"WCL token endpoint returned {response.status_code}: "
                f"{response.text[:200]}"
            )
        body = response.json()
        token = body.get("access_token")
        expires_in = body.get("expires_in", 0)
        if not isinstance(token, str) or not token:
            raise OAuthError("WCL token response missing access_token")
        if not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise OAuthError("WCL token response missing expires_in")
        return _CachedToken(access_token=token, expires_at=time.time() + float(expires_in))
