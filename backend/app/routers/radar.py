"""API routes for Radar: curated RSS source CRUD, manual interest boost
topics, and (Task 8) the refresh/list/add/dismiss recommendation flow. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response

from app.core.config import get_data_root
from app.radar_store.store import (
    delete_boost_topic,
    delete_feed_source,
    get_boost_topic,
    get_feed_source,
    init_db,
    insert_boost_topic,
    insert_feed_source,
    list_boost_topics,
    list_feed_sources,
    radar_db_path,
    update_feed_source,
)
from app.schemas.radar import (
    BoostTopic,
    BoostTopicCreateRequest,
    BoostTopicList,
    FeedSource,
    FeedSourceCreateRequest,
    FeedSourceList,
    FeedSourceUpdateRequest,
)

router = APIRouter(prefix="/radar", tags=["radar"])


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
