"""RSS/Atom feed fetching for Radar. Fetches the feed's raw XML through the
existing SSRF-guarded app.ingestion.fetcher.fetch_url (same guard used for
every other outbound fetch in this codebase — no new fetch path), then
parses it with feedparser. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

from datetime import datetime, timezone

import feedparser

from app.ingestion.fetcher import FetchError, fetch_url


class FeedFetchError(Exception):
    pass


def fetch_feed_items(url: str) -> list[dict]:
    """Returns a list of {"url", "title", "summary", "published_at"} dicts,
    one per feed entry. Raises FeedFetchError on any fetch failure or on a
    feed that feedparser cannot parse at all (its bozo flag with no usable
    entries) — callers treat this as a per-source failure that must not
    abort the whole refresh run."""
    try:
        raw = fetch_url(url)
    except FetchError as exc:
        raise FeedFetchError(f"Failed to fetch feed {url}: {exc}") from exc

    parsed = feedparser.parse(raw)
    if parsed.bozo and not parsed.entries:
        raise FeedFetchError(f"Feed at {url} could not be parsed: {parsed.bozo_exception}")

    items = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        published_at = None
        if entry.get("published_parsed"):
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        items.append(
            {
                "url": link,
                "title": title,
                "summary": entry.get("summary", ""),
                "published_at": published_at,
            }
        )
    return items
