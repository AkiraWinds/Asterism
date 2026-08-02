"""Pydantic models for Radar: feed sources, boost topics, and ranked
recommendation items. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

from pydantic import BaseModel


class FeedSource(BaseModel):
    id: str
    name: str
    url: str
    enabled: bool
    last_fetched_at: str | None = None
    last_fetch_status: str | None = None
    last_fetch_error: str | None = None
    created_at: str


class FeedSourceCreateRequest(BaseModel):
    name: str
    url: str


class FeedSourceUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


class FeedSourceList(BaseModel):
    sources: list[FeedSource] = []


class BoostTopic(BaseModel):
    id: str
    term: str
    created_at: str


class BoostTopicCreateRequest(BaseModel):
    term: str


class BoostTopicList(BaseModel):
    topics: list[BoostTopic] = []


class RadarItem(BaseModel):
    id: str
    source_id: str
    url: str
    title: str
    summary: str
    published_at: str | None = None
    relevance_score: float
    quality_score: float
    reasoning: str
    status: str
    added_source_id: str | None = None
    created_at: str


class RadarItemList(BaseModel):
    items: list[RadarItem] = []


class RadarRefreshSummary(BaseModel):
    per_source: dict[str, dict] = {}
