from pathlib import Path

from app.providers.base import Provider
from app.radar.fetcher import FeedFetchError
from app.radar.pipeline import refresh_radar
from app.radar_store.store import (
    delete_feed_source,
    init_db,
    insert_feed_source,
    list_feed_sources,
    list_new_radar_items,
    radar_db_path,
)


class _StubProvider(Provider):
    def complete(self, prompt: str) -> str:
        return '{"relevance_score": 0.8, "quality_score": 0.7, "reasoning": "Relevant and substantive."}'


def _setup(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    # init_db seeds DEFAULT_FEED_SOURCES on first run; clear them so these
    # tests only see the sources they explicitly insert.
    for source in list_feed_sources(db_path):
        delete_feed_source(db_path, source["id"])
    return db_path


def test_refresh_radar_happy_path(tmp_path: Path, monkeypatch):
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Good Source", "https://good.example.com/rss", "2026-08-02T00:00:00+00:00")

    monkeypatch.setattr(
        "app.radar.pipeline.fetch_feed_items",
        lambda url: [{"url": "https://good.example.com/post", "title": "A Post", "summary": "About agents.", "published_at": None}],
    )
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr(
        "app.radar.pipeline.coarse_filter",
        lambda graph_db_path, api_key, items, boost_terms, top_n=20: [{**items[0], "_coarse_score": 0.9}],
    )
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr(
        "app.radar.pipeline.judge_item",
        lambda provider, text, source_name, terms: {"relevance_score": 0.8, "quality_score": 0.7, "reasoning": "Relevant and substantive."},
    )

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Good Source"]["fetched"] == 1
    assert summary["Good Source"]["new"] == 1
    assert summary["Good Source"]["error"] is None

    items = list_new_radar_items(db_path, cutoff_iso="2020-01-01T00:00:00+00:00")
    assert len(items) == 1
    assert items[0]["relevance_score"] == 0.8


def test_refresh_radar_one_bad_source_does_not_block_others(tmp_path: Path, monkeypatch):
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "bad", "Bad Source", "https://bad.example.com/rss", "2026-08-02T00:00:00+00:00")
    insert_feed_source(db_path, "good", "Good Source", "https://good.example.com/rss", "2026-08-02T00:00:00+00:00")

    def _fetch(url):
        if "bad" in url:
            raise FeedFetchError("feed is broken")
        return []

    monkeypatch.setattr("app.radar.pipeline.fetch_feed_items", _fetch)
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr("app.radar.pipeline.coarse_filter", lambda *a, **k: [])

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Bad Source"]["error"] is not None
    assert summary["Good Source"]["error"] is None


def test_refresh_radar_disabled_source_is_skipped(tmp_path: Path, monkeypatch):
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Disabled Source", "https://disabled.example.com/rss", "2026-08-02T00:00:00+00:00")
    from app.radar_store.store import update_feed_source

    update_feed_source(db_path, "s1", enabled=False)

    fetch_called = []
    monkeypatch.setattr("app.radar.pipeline.fetch_feed_items", lambda url: fetch_called.append(url) or [])

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert fetch_called == []
    assert "Disabled Source" not in summary
