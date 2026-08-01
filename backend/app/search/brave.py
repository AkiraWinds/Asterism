"""Brave Search web-search client, used by the extraction/watchlist reference
resolution chain to ground a term's definition when it isn't already in the
concept graph. A fresh backend-native client — legacy src/lib/search.ts (frozen
per the 2026-08-01 legacy-freeze decision) is referenced as a pattern only, not
reused code. See docs/superpowers/specs/2026-08-01-entity-extraction-reference-lookup-design.md.
"""

import httpx

from app.providers.base import ProviderError

_BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def search_web(api_key: str, query: str, count: int = 3) -> list[dict]:
    """Returns up to `count` results as {"title", "url", "description"} dicts.
    Returns [] on a zero-result search; raises ProviderError on a non-2xx
    response (auth failure, rate limit, etc.) or network-level failures (timeout,
    connection refused, etc.) — callers (the resolution chain) treat that the
    same as "web search unavailable" and fall through to the next step, never
    surfacing a raw HTTP error to the end user."""
    try:
        response = httpx.get(
            _BRAVE_WEB_SEARCH_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": count},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise ProviderError(f"Brave Search request failed: {exc}")

    if response.status_code != 200:
        raise ProviderError(f"Brave Search API error: {response.status_code} {response.text[:200]}")

    results = response.json().get("web", {}).get("results", [])
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")}
        for r in results
    ]
