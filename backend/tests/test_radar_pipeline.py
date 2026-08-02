from pathlib import Path

from app.providers.base import Provider, ProviderConfigError, ProviderMissingError
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


def test_refresh_radar_coarse_filter_provider_error_isolated_to_source(tmp_path: Path, monkeypatch):
    """coarse_filter's embed_text call can raise ProviderConfigError (bad
    embeddings key) or a transient ProviderError. That must be recorded as
    this source's error and must not abort the whole run."""
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "bad", "Bad Embeds Source", "https://bad.example.com/rss", "2026-08-02T00:00:00+00:00")
    insert_feed_source(db_path, "good", "Good Source", "https://good.example.com/rss", "2026-08-02T00:00:00+00:00")

    def _fetch(url):
        return [{"url": f"{url}/post", "title": "A Post", "summary": "About agents.", "published_at": None}]

    def _coarse_filter(graph_db_path, api_key, items, boost_terms, top_n=20):
        if items and "bad" in items[0]["url"]:
            raise ProviderConfigError("embeddings API key is invalid")
        return [{**items[0], "_coarse_score": 0.9}] if items else []

    monkeypatch.setattr("app.radar.pipeline.fetch_feed_items", _fetch)
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr("app.radar.pipeline.coarse_filter", _coarse_filter)
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr(
        "app.radar.pipeline.judge_item",
        lambda provider, text, source_name, terms: {"relevance_score": 0.8, "quality_score": 0.7, "reasoning": "ok"},
    )

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Bad Embeds Source"]["error"] is not None
    assert summary["Good Source"]["error"] is None
    assert summary["Good Source"]["new"] == 1


def test_refresh_radar_judge_provider_missing_error_isolated_to_source(tmp_path: Path, monkeypatch):
    """judge_item raising ProviderMissingError/ProviderConfigError signals a
    systemic provider misconfiguration, not a per-item content failure — it
    must propagate to source-level error handling (not be silently caught by
    the per-item except-and-skip), and must still not abort the whole run."""
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Misconfigured Source", "https://misconfigured.example.com/rss", "2026-08-02T00:00:00+00:00")
    insert_feed_source(db_path, "s2", "Good Source", "https://good.example.com/rss", "2026-08-02T00:00:00+00:00")

    def _fetch(url):
        return [{"url": f"{url}/post", "title": "A Post", "summary": "About agents.", "published_at": None}]

    def _judge_item(provider, text, source_name, terms):
        if source_name == "Misconfigured Source":
            raise ProviderMissingError("chat provider is not configured")
        return {"relevance_score": 0.8, "quality_score": 0.7, "reasoning": "ok"}

    monkeypatch.setattr("app.radar.pipeline.fetch_feed_items", _fetch)
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr(
        "app.radar.pipeline.coarse_filter",
        lambda graph_db_path, api_key, items, boost_terms, top_n=20: [{**items[0], "_coarse_score": 0.9}] if items else [],
    )
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr("app.radar.pipeline.judge_item", _judge_item)

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Misconfigured Source"]["error"] is not None
    assert summary["Misconfigured Source"]["new"] == 0
    assert summary["Good Source"]["error"] is None
    assert summary["Good Source"]["new"] == 1
