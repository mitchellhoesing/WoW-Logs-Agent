"""Verify WCL + Anthropic credentials work. Run: python scripts/check_credentials.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx
from anthropic import Anthropic

from wowlogs_agent.infrastructure.config import Settings


def check_wcl(settings: Settings) -> None:
    print("[WCL] Requesting OAuth token...", end=" ")
    resp = httpx.post(
        settings.wcl_token_url,
        data={"grant_type": "client_credentials"},
        auth=(settings.wcl_client_id, settings.wcl_client_secret_value),
        timeout=15.0,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print("OK")

    print("[WCL] Probing GraphQL (rateLimitData)...", end=" ")
    gql = httpx.post(
        settings.wcl_endpoint,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "{ rateLimitData { limitPerHour pointsSpentThisHour } }"},
        timeout=15.0,
    )
    gql.raise_for_status()
    data = gql.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    rl = data["data"]["rateLimitData"]
    print(f"OK (limit {rl['limitPerHour']}/hr, spent {rl['pointsSpentThisHour']})")


def check_anthropic(settings: Settings) -> None:
    print(f"[Anthropic] Calling {settings.llm_model}...", end=" ")
    client = Anthropic(api_key=settings.anthropic_api_key_value)
    msg = client.messages.create(
        model=settings.llm_model,
        max_tokens=16,
        messages=[{"role": "user", "content": "Reply with the single word: pong"}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    print(f"OK (reply: {text!r})")


def main() -> int:
    settings = Settings.load()

    missing = []
    if not settings.wcl_client_id or settings.wcl_client_id.startswith("your_"):
        missing.append("WCL_CLIENT_ID")
    if not settings.wcl_client_secret_value or settings.wcl_client_secret_value.startswith("your_"):
        missing.append("WCL_CLIENT_SECRET")
    if not settings.anthropic_api_key_value or settings.anthropic_api_key_value.startswith("your_"):
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"ERROR: placeholder/missing values in .env: {', '.join(missing)}")
        return 2

    try:
        check_wcl(settings)
        check_anthropic(settings)
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP error: {e.response.status_code} {e.response.text[:200]}")
        return 1
    except Exception as e:
        print(f"\nFailed: {type(e).__name__}: {e}")
        return 1

    print("\nAll credentials OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
