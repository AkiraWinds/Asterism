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
from app.providers.base import Provider, ProviderConfigError, ProviderMissingError
from app.radar.fetcher import fetch_feed_items
from app.radar.judge import judge_item
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

# Coarse-filtered candidates that still judge as low-relevance (e.g. on a
# fresh install with an empty concept graph and no boost topics, where every
# coarse score is 0.0) are noise, not a recommendation — don't persist them
# regardless of how they ranked in the shortlist.
RADAR_RELEVANCE_FLOOR = 0.15


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh_radar(data_root: Path, provider: Provider, embeddings_api_key: str) -> dict:
    """Run one Radar refresh pass across all enabled feed sources.

    Returns {source_name: {"fetched": int, "new": int, "error": str | None}}.
    "new" means "how many of this source's items ended up in the final
    persisted set" — since coarse-filtering happens once per RUN (not once
    per source, see below), a source can legitimately end up with new == 0
    even on a clean fetch if none of its items made the global top-N cut.

    Runs in two passes:
      1. Fetch + dedup each source's feed. A source's own fetch health
         (ok/error) is recorded here, independent of what happens to its
         items afterwards. A per-source failure (bad feed XML, a malformed
         entry, a network error) is recorded on that source and does not
         abort the run for other sources.
      2. Coarse-filter the COMBINED candidate pool from every source ONCE,
         then fetch full content + LLM-judge just that one shortlist (at
         most top_n items total per run, not top_n per source). Items whose
         judged relevance falls below RADAR_RELEVANCE_FLOOR are dropped
         rather than persisted. A per-item failure is logged and skipped; a
         systemic provider misconfiguration surfaced while judging is
         additionally recorded against that item's source for visibility,
         but still doesn't stop the rest of the shortlist from being judged.
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
    combined_items = []  # new items from every enabled source, tagged with their source

    # Pass 1: fetch + dedup. A source's fetch status is settled here and
    # does not depend on later coarse-filter/judge outcomes.
    for source in list_feed_sources(db_path):
        if not source["enabled"]:
            continue

        try:
            raw_items = fetch_feed_items(source["url"], data_root=data_root)
            new_items = filter_new_items(raw_items, seen_urls)
        except Exception as exc:  # noqa: BLE001 - any per-source fetch/dedup failure (bad feed XML, malformed entry, network error, ...) must not abort the run
            logger.warning("Radar fetch failed source=%s error=%s", source["name"], exc)
            update_feed_source_fetch_status(
                db_path, source["id"], status="error", error=str(exc), fetched_at=_now_iso()
            )
            summary[source["name"]] = {"fetched": 0, "new": 0, "error": str(exc)}
            continue

        update_feed_source_fetch_status(db_path, source["id"], status="ok", error=None, fetched_at=_now_iso())
        summary[source["name"]] = {"fetched": len(raw_items), "new": 0, "error": None}
        for item in new_items:
            combined_items.append({**item, "_source_id": source["id"], "_source_name": source["name"]})

    # Pass 2: coarse-filter the combined pool exactly once per run (not once
    # per source), so at most top_n items get the expensive full-content
    # fetch + LLM judgment regardless of how many sources are configured.
    # coarse_filter calls embed_text (ProviderConfigError on a bad/expired
    # embeddings key, or the broader ProviderError) and nearest_neighbors
    # (e.g. sqlite3.OperationalError if graph.db is locked by a concurrent
    # writer) — none of that is attributable to a single source anymore
    # since this is now a single run-level call, so any failure here just
    # means no items get judged this run; the pass-1 fetch-status bookkeeping
    # above is unaffected.
    try:
        shortlist = coarse_filter(g_db_path, embeddings_api_key, combined_items, boost_terms)
    except Exception as exc:  # noqa: BLE001 - a run-level coarse-filter failure must not abort the run or discard pass-1 results
        logger.warning("Radar coarse filter failed error=%s", exc)
        shortlist = []

    for item in shortlist:
        source_name = item["_source_name"]
        try:
            html = fetch_url(item["url"], data_root=data_root)
            article_text = extract_content(html, item["url"], data_root)
            judgment = judge_item(provider, article_text, source_name, boost_terms)
        except (ProviderMissingError, ProviderConfigError) as exc:
            # Systemic provider misconfiguration, not a per-item content
            # problem — record it against this item's source for
            # visibility, but keep judging the rest of the shortlist (which
            # may include items from other, healthy sources).
            logger.warning("Radar judgment failed url=%s error=%s", item["url"], exc)
            summary[source_name]["error"] = str(exc)
            continue
        except Exception as exc:  # noqa: BLE001 - any other per-item failure must not break the run
            logger.warning("Radar judgment failed url=%s error=%s", item["url"], exc)
            continue

        if judgment["relevance_score"] < RADAR_RELEVANCE_FLOOR:
            # Persist as 'rejected' rather than dropping it — list_new_radar_items
            # only returns status='new', so GET /radar is unaffected, but this
            # keeps the item in list_all_radar_item_urls's dedup set so it's never
            # re-fetched/re-embedded/re-judged by the LLM on a future refresh.
            insert_radar_item(
                db_path,
                item_id=uuid.uuid4().hex[:12],
                source_id=item["_source_id"],
                url=item["url"],
                title=item["title"],
                summary=item.get("summary", ""),
                published_at=item.get("published_at"),
                relevance_score=judgment["relevance_score"],
                quality_score=judgment["quality_score"],
                reasoning=judgment["reasoning"],
                created_at=_now_iso(),
                status="rejected",
            )
            continue

        inserted = insert_radar_item(
            db_path,
            item_id=uuid.uuid4().hex[:12],
            source_id=item["_source_id"],
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
            summary[source_name]["new"] += 1
            seen_urls.add(item["url"])

    return summary
