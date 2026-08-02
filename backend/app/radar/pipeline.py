"""Orchestrates one Radar refresh run: fetch each enabled source's RSS feed,
dedup against the library and prior runs, coarse-filter by embedding
similarity, fetch full content + LLM-judge the shortlist, and persist
survivors. A per-source or per-item failure is recorded/skipped rather than
aborting the whole run. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.graph_store.store import graph_db_path
from app.graph_store.store import init_db as init_graph_db
from app.ingestion.extractor import extract_content
from app.ingestion.fetcher import fetch_url
from app.providers.base import Provider
from app.radar.fetcher import FeedFetchError, fetch_feed_items
from app.radar.judge import JudgeError, judge_item
from app.radar.ranking import coarse_filter, filter_new_items
from app.radar_store.store import (
    init_db,
    insert_radar_item,
    list_all_radar_item_urls,
    list_boost_topics,
    list_feed_sources,
    radar_db_path,
    update_feed_source_fetch_status,
)
from app.repositories.source_repository import list_source_urls

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh_radar(data_root: Path, provider: Provider, embeddings_api_key: str) -> dict:
    """Run one Radar refresh pass across all enabled feed sources.

    Returns {source_name: {"fetched": int, "new": int, "error": str | None}}.
    A source that fails to fetch is recorded with its error and skipped; a
    shortlisted item that fails full-content fetch/extraction/judging is
    logged and skipped — neither aborts the run for other sources/items.
    """
    db_path = radar_db_path(data_root)
    init_db(db_path)
    g_db_path = graph_db_path(data_root)
    init_graph_db(g_db_path)

    # Dedup against both the existing library (already-captured sources) and
    # prior radar runs (already-surfaced-but-not-yet-added items).
    seen_urls = list_source_urls(data_root) | list_all_radar_item_urls(db_path)
    boost_terms = [t["term"] for t in list_boost_topics(db_path)]

    summary = {}
    for source in list_feed_sources(db_path):
        if not source["enabled"]:
            continue

        try:
            raw_items = fetch_feed_items(source["url"])
        except FeedFetchError as exc:
            logger.warning("Radar fetch failed source=%s error=%s", source["name"], exc)
            update_feed_source_fetch_status(
                db_path, source["id"], status="error", error=str(exc), fetched_at=_now_iso()
            )
            summary[source["name"]] = {"fetched": 0, "new": 0, "error": str(exc)}
            continue

        new_items = filter_new_items(raw_items, seen_urls)
        shortlist = coarse_filter(g_db_path, embeddings_api_key, new_items, boost_terms)

        new_count = 0
        for item in shortlist:
            try:
                html = fetch_url(item["url"])
                article_text = extract_content(html, item["url"], data_root)
                judgment = judge_item(provider, article_text, source["name"], boost_terms)
            except Exception as exc:  # noqa: BLE001 - any per-item failure must not break the run
                logger.warning("Radar judgment failed url=%s error=%s", item["url"], exc)
                continue

            inserted = insert_radar_item(
                db_path,
                item_id=uuid.uuid4().hex[:12],
                source_id=source["id"],
                url=item["url"],
                title=item["title"],
                summary=item.get("summary", ""),
                published_at=item.get("published_at"),
                relevance_score=judgment["relevance_score"],
                quality_score=judgment["quality_score"],
                reasoning=judgment["reasoning"],
                created_at=_now_iso(),
            )
            if inserted:
                new_count += 1
                seen_urls.add(item["url"])

        update_feed_source_fetch_status(db_path, source["id"], status="ok", error=None, fetched_at=_now_iso())
        summary[source["name"]] = {"fetched": len(raw_items), "new": new_count, "error": None}

    return summary
