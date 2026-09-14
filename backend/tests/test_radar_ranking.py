from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.radar.ranking import RADAR_RECENCY_FLOOR, _recency_weight, coarse_filter, filter_new_items
from app.repositories.source_repository import create_source_from_url, list_source_urls


def test_filter_new_items_drops_seen_urls():
    items = [
        {"url": "https://example.com/a", "title": "A"},
        {"url": "https://example.com/b", "title": "B"},
    ]
    result = filter_new_items(items, seen_urls={"https://example.com/a"})
    assert [i["url"] for i in result] == ["https://example.com/b"]


def test_list_source_urls_reads_from_meta_json(tmp_path: Path):
    create_source_from_url(tmp_path, "https://example.com/already-saved", "Title", "<html></html>", "content")

    assert list_source_urls(tmp_path) == {"https://example.com/already-saved"}


def test_coarse_filter_ranks_by_similarity_and_truncates(tmp_path: Path, monkeypatch):
    # Each item's embedding is just [similarity_to_graph] for a deterministic test —
    # nearest_neighbors and embed_text are both stubbed so no real network/graph.db lookups happen.
    monkeypatch.setattr(
        "app.radar.ranking.embed_text",
        lambda api_key, text, **_kwargs: [0.9] if "close" in text else [0.1],
    )
    monkeypatch.setattr(
        "app.radar.ranking.nearest_neighbors",
        lambda db_path, embedding, top_k=1: [({"term": "x", "definition": "y", "golden": False}, embedding[0], embedding[0])],
    )

    items = [
        {"url": "https://example.com/close", "title": "close match", "summary": ""},
        {"url": "https://example.com/far", "title": "far match", "summary": ""},
    ]

    result = coarse_filter(tmp_path / "graph.db", "fake-key", items, boost_terms=[], top_n=1)

    assert len(result) == 1
    assert result[0]["url"] == "https://example.com/close"
    assert "_coarse_score" in result[0]


def test_coarse_filter_default_return_shape_is_unchanged(tmp_path: Path, monkeypatch):
    # return_rejected defaults to False — existing callers (and this test) must keep
    # getting back a plain list, not a tuple, so the contract stays backward-compatible.
    monkeypatch.setattr("app.radar.ranking.embed_text", lambda api_key, text, **_kwargs: [0.5])
    monkeypatch.setattr("app.radar.ranking.nearest_neighbors", lambda db_path, embedding, top_k=1: [])

    result = coarse_filter(tmp_path / "graph.db", "fake-key", [{"url": "u", "title": "t", "summary": ""}], boost_terms=[])

    assert isinstance(result, list)
    assert result[0]["url"] == "u"


def test_coarse_filter_return_rejected_splits_shortlist_and_below_cut(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "app.radar.ranking.embed_text",
        lambda api_key, text, **_kwargs: [0.9] if "close" in text else [0.1],
    )
    monkeypatch.setattr(
        "app.radar.ranking.nearest_neighbors",
        lambda db_path, embedding, top_k=1: [({"term": "x", "definition": "y", "golden": False}, embedding[0], embedding[0])],
    )

    items = [
        {"url": "https://example.com/close", "title": "close match", "summary": ""},
        {"url": "https://example.com/far", "title": "far match", "summary": ""},
    ]

    shortlist, below_cut = coarse_filter(
        tmp_path / "graph.db", "fake-key", items, boost_terms=[], top_n=1, return_rejected=True,
    )

    assert [i["url"] for i in shortlist] == ["https://example.com/close"]
    assert [i["url"] for i in below_cut] == ["https://example.com/far"]
    assert "_coarse_score" in below_cut[0]


def test_recency_weight_is_full_for_missing_published_at():
    # Some feeds omit published_at entirely — no age signal means no penalty.
    assert _recency_weight(None) == 1.0


def test_recency_weight_is_full_for_a_brand_new_item():
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    assert _recency_weight(now.isoformat(), now=now) == 1.0


def test_recency_weight_decays_with_age_and_is_floored():
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    half_life_ago = (now - timedelta(days=3)).isoformat()
    ancient = (now - timedelta(days=365)).isoformat()

    assert _recency_weight(half_life_ago, now=now) == pytest.approx(0.5, abs=1e-6)
    # Floored, not zeroed — a much older item stays deprioritized, not eliminated.
    assert _recency_weight(ancient, now=now) == RADAR_RECENCY_FLOOR


def test_coarse_filter_ranks_recent_item_above_older_equally_similar_item(tmp_path: Path, monkeypatch):
    # Both items embed identically (same similarity to the graph) so the only
    # thing that can separate them is the recency weight applied on top.
    monkeypatch.setattr("app.radar.ranking.embed_text", lambda api_key, text, **_kwargs: [0.9])
    monkeypatch.setattr(
        "app.radar.ranking.nearest_neighbors",
        lambda db_path, embedding, top_k=1: [({"term": "x", "definition": "y", "golden": False}, embedding[0], embedding[0])],
    )

    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    items = [
        {"url": "https://example.com/old", "title": "old", "summary": "", "published_at": (now - timedelta(days=30)).isoformat()},
        {"url": "https://example.com/new", "title": "new", "summary": "", "published_at": now.isoformat()},
    ]

    result = coarse_filter(tmp_path / "graph.db", "fake-key", items, boost_terms=[], top_n=2)

    assert [i["url"] for i in result] == ["https://example.com/new", "https://example.com/old"]
