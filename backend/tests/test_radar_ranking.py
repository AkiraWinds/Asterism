from pathlib import Path

from app.radar.ranking import coarse_filter, filter_new_items
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
        lambda api_key, text: [0.9] if "close" in text else [0.1],
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
