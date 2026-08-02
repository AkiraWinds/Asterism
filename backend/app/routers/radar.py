"""API routes for Radar: curated RSS source CRUD, manual interest boost
topics, and the refresh/list/add/dismiss recommendation flow. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Response

from app.core.config import get_data_root
from app.ingestion.extractor import extract_content
from app.ingestion.fetcher import FetchError, fetch_url
from app.ingestion.title import extract_title
from app.providers.base import ProviderError
from app.providers.factory import build_provider
from app.radar.pipeline import refresh_radar
from app.radar_store.store import (
    delete_boost_topic,
    delete_feed_source,
    get_boost_topic,
    get_feed_source,
    get_radar_item,
    init_db,
    insert_boost_topic,
    insert_feed_source,
    list_boost_topics,
    list_feed_sources,
    list_new_radar_items,
    radar_db_path,
    update_feed_source,
    update_radar_item_status,
)
from app.repositories.config_repository import ConfigError, load_config, load_embeddings_api_key
from app.repositories.source_repository import create_source_from_url
from app.schemas.radar import (
    BoostTopic,
    BoostTopicCreateRequest,
    BoostTopicList,
    FeedSource,
    FeedSourceCreateRequest,
    FeedSourceList,
    FeedSourceUpdateRequest,
    RadarItem,
    RadarItemList,
    RadarRefreshSummary,
)

router = APIRouter(prefix="/radar", tags=["radar"])

# Radar items are ephemeral recommendations, not a permanent archive — items
# still 'new' after this many days drop out of GET /radar (though they stay
# in radar.db for dedup purposes via list_all_radar_item_urls).
RADAR_ITEM_EXPIRY_DAYS = 14


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_db():
    # init_db is idempotent (CREATE TABLE IF NOT EXISTS + seed-only-if-empty),
    # so calling it on every request is cheap and keeps each endpoint
    # self-contained without a startup hook.
    db_path = radar_db_path(get_data_root())
    init_db(db_path)
    return db_path


@router.get("/sources", response_model=FeedSourceList)
def get_sources_endpoint() -> FeedSourceList:
    db_path = _ensure_db()
    return FeedSourceList(sources=list_feed_sources(db_path))


@router.post("/sources", response_model=FeedSource)
def post_source_endpoint(payload: FeedSourceCreateRequest) -> FeedSource:
    db_path = _ensure_db()
    source_id = f"fs_{uuid.uuid4().hex[:10]}"
    insert_feed_source(db_path, source_id, payload.name, payload.url, _now_iso())
    return FeedSource(**get_feed_source(db_path, source_id))


@router.patch("/sources/{source_id}", response_model=FeedSource)
def patch_source_endpoint(source_id: str, payload: FeedSourceUpdateRequest) -> FeedSource:
    db_path = _ensure_db()
    if get_feed_source(db_path, source_id) is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    update_feed_source(db_path, source_id, name=payload.name, url=payload.url, enabled=payload.enabled)
    return FeedSource(**get_feed_source(db_path, source_id))


@router.delete("/sources/{source_id}", status_code=204)
def delete_source_endpoint(source_id: str):
    db_path = _ensure_db()
    if get_feed_source(db_path, source_id) is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    delete_feed_source(db_path, source_id)
    return Response(status_code=204)


@router.get("/boost-topics", response_model=BoostTopicList)
def get_boost_topics_endpoint() -> BoostTopicList:
    db_path = _ensure_db()
    return BoostTopicList(topics=list_boost_topics(db_path))


@router.post("/boost-topics", response_model=BoostTopic)
def post_boost_topic_endpoint(payload: BoostTopicCreateRequest) -> BoostTopic:
    db_path = _ensure_db()
    topic_id = f"bt_{uuid.uuid4().hex[:10]}"
    created_at = _now_iso()
    insert_boost_topic(db_path, topic_id, payload.term, created_at)
    return BoostTopic(id=topic_id, term=payload.term, created_at=created_at)


@router.delete("/boost-topics/{topic_id}", status_code=204)
def delete_boost_topic_endpoint(topic_id: str):
    db_path = _ensure_db()
    if get_boost_topic(db_path, topic_id) is None:
        raise HTTPException(status_code=404, detail="Boost topic not found")
    delete_boost_topic(db_path, topic_id)
    return Response(status_code=204)


@router.post("/refresh", response_model=RadarRefreshSummary)
def post_refresh_endpoint() -> RadarRefreshSummary:
    data_root = get_data_root()
    try:
        config = load_config(data_root)
        embeddings_api_key = load_embeddings_api_key(data_root)
    except ConfigError as exc:
        # Same failure mode as the CLI twin (scripts/radar_refresh.py), which
        # catches this and reports it as a JSON error rather than crashing —
        # both entry points to the same operation should degrade the same way.
        raise HTTPException(status_code=400, detail=str(exc))
    provider = build_provider(config, data_root)
    summary = refresh_radar(data_root, provider, embeddings_api_key)
    return RadarRefreshSummary(per_source=summary)


@router.get("", response_model=RadarItemList)
def get_radar_items_endpoint() -> RadarItemList:
    db_path = _ensure_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RADAR_ITEM_EXPIRY_DAYS)).isoformat()
    return RadarItemList(items=[RadarItem(**i) for i in list_new_radar_items(db_path, cutoff)])


@router.post("/items/{item_id}/add")
def post_add_item_endpoint(item_id: str):
    db_path = _ensure_db()
    item = get_radar_item(db_path, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Radar item not found")

    data_root = get_data_root()
    try:
        html = fetch_url(item["url"])
        title = extract_title(html, item["url"]) or item["title"]
        content = extract_content(html, item["url"], data_root)
        record = create_source_from_url(data_root, item["url"], title, html, content)
    except (FetchError, ConfigError, ProviderError, OSError) as exc:
        # Not the full structured-error mapping sources.py's create_source_endpoint
        # has (deferred to the frontend follow-up plan) — one combined 502 is
        # proportionate for this reuse endpoint. update_radar_item_status is never
        # reached here, so the item stays 'new' and safely retryable.
        raise HTTPException(status_code=502, detail=f"Failed to add item: {exc}")

    update_radar_item_status(db_path, item_id, status="added", added_source_id=record.id)
    return {"id": record.id, "title": record.title}


@router.post("/items/{item_id}/dismiss", status_code=204)
def post_dismiss_item_endpoint(item_id: str):
    db_path = _ensure_db()
    item = get_radar_item(db_path, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Radar item not found")
    if item["status"] == "added":
        # update_radar_item_status does an unconditional SET added_source_id
        # = ? (default None) — dismissing an already-added item would wipe
        # out the link to the library source it was added as.
        raise HTTPException(status_code=409, detail="Cannot dismiss an item that has already been added to the library")
    update_radar_item_status(db_path, item_id, status="dismissed")
    return Response(status_code=204)
