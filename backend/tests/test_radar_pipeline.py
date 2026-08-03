from pathlib import Path

from app.providers.base import Provider, ProviderMissingError
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
        lambda graph_db_path, api_key, items, boost_terms, top_n=20: [{**i, "_coarse_score": 0.9} for i in items],
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


def test_refresh_radar_coarse_filter_runtime_error_does_not_abort_run(tmp_path: Path, monkeypatch):
    """coarse_filter now runs exactly once per run over the combined
    candidate pool from every source (not once per source), so a failure
    inside it (embed_text raising ProviderConfigError/ProviderError, or
    nearest_neighbors raising e.g. sqlite3.OperationalError on a locked
    graph.db) is a run-level event, not attributable to one source. It must
    not abort the whole run, and must not wipe out the per-source
    fetch-status bookkeeping already recorded in pass 1."""
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Source One", "https://one.example.com/rss", "2026-08-02T00:00:00+00:00")
    insert_feed_source(db_path, "s2", "Source Two", "https://two.example.com/rss", "2026-08-02T00:00:00+00:00")

    def _fetch(url):
        return [{"url": f"{url}/post", "title": "A Post", "summary": "About agents.", "published_at": None}]

    def _coarse_filter(graph_db_path, api_key, items, boost_terms, top_n=20):
        raise RuntimeError("graph.db is locked")

    monkeypatch.setattr("app.radar.pipeline.fetch_feed_items", _fetch)
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr("app.radar.pipeline.coarse_filter", _coarse_filter)

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Source One"]["error"] is None
    assert summary["Source Two"]["error"] is None
    assert summary["Source One"]["new"] == 0
    assert summary["Source Two"]["new"] == 0


def test_refresh_radar_calls_coarse_filter_once_per_run_not_per_source(tmp_path: Path, monkeypatch):
    """coarse_filter's top_n (default 20) is meant to cap candidates per RUN,
    not per source — calling it once per source would let up to top_n *
    num_sources items through to the expensive full-content-fetch + judge
    step. Assert it's called exactly once regardless of source count."""
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Source One", "https://one.example.com/rss", "2026-08-02T00:00:00+00:00")
    insert_feed_source(db_path, "s2", "Source Two", "https://two.example.com/rss", "2026-08-02T00:00:00+00:00")

    def _fetch(url):
        return [{"url": f"{url}/post", "title": "A Post", "summary": "About agents.", "published_at": None}]

    call_count = {"n": 0}

    def _coarse_filter(graph_db_path, api_key, items, boost_terms, top_n=20):
        call_count["n"] += 1
        return [{**i, "_coarse_score": 0.9} for i in items]

    monkeypatch.setattr("app.radar.pipeline.fetch_feed_items", _fetch)
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr("app.radar.pipeline.coarse_filter", _coarse_filter)
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr(
        "app.radar.pipeline.judge_item",
        lambda provider, text, source_name, terms: {"relevance_score": 0.8, "quality_score": 0.7, "reasoning": "ok"},
    )

    refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert call_count["n"] == 1


def test_refresh_radar_skips_items_below_relevance_floor(tmp_path: Path, monkeypatch):
    """A coarse-filtered candidate that judges as low-relevance (e.g. on a
    fresh install with an empty concept graph, where every coarse score is
    0.0) must not be persisted — that's noise, not a recommendation."""
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Source One", "https://one.example.com/rss", "2026-08-02T00:00:00+00:00")

    monkeypatch.setattr(
        "app.radar.pipeline.fetch_feed_items",
        lambda url: [{"url": "https://one.example.com/post", "title": "A Post", "summary": "About agents.", "published_at": None}],
    )
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr(
        "app.radar.pipeline.coarse_filter",
        lambda graph_db_path, api_key, items, boost_terms, top_n=20: [{**i, "_coarse_score": 0.0} for i in items],
    )
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr(
        "app.radar.pipeline.judge_item",
        lambda provider, text, source_name, terms: {"relevance_score": 0.05, "quality_score": 0.7, "reasoning": "Not really relevant."},
    )

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Source One"]["new"] == 0
    assert list_new_radar_items(db_path, cutoff_iso="2020-01-01T00:00:00+00:00") == []


def test_refresh_radar_persists_below_floor_items_as_rejected(tmp_path: Path, monkeypatch):
    """A below-floor item must still be written to radar_items (status='rejected')
    so it's excluded from cross-run dedup re-fetching, instead of being silently
    dropped and re-judged by the LLM on every future refresh."""
    db_path = _setup(tmp_path)
    insert_feed_source(db_path, "s1", "Source One", "https://one.example.com/rss", "2026-08-02T00:00:00+00:00")

    monkeypatch.setattr(
        "app.radar.pipeline.fetch_feed_items",
        lambda url: [{"url": "https://one.example.com/post", "title": "A Post", "summary": "About agents.", "published_at": None}],
    )
    monkeypatch.setattr("app.radar.pipeline.list_source_urls", lambda data_root: set())
    monkeypatch.setattr(
        "app.radar.pipeline.coarse_filter",
        lambda graph_db_path, api_key, items, boost_terms, top_n=20: [{**i, "_coarse_score": 0.0} for i in items],
    )
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr(
        "app.radar.pipeline.judge_item",
        lambda provider, text, source_name, terms: {"relevance_score": 0.05, "quality_score": 0.7, "reasoning": "Not really relevant."},
    )

    refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    from app.radar_store.store import list_all_radar_item_urls

    # Still excluded from GET /radar (list_new_radar_items filters status='new')...
    assert list_new_radar_items(db_path, cutoff_iso="2020-01-01T00:00:00+00:00") == []
    # ...but present for cross-run dedup, so it's never re-judged again.
    assert "https://one.example.com/post" in list_all_radar_item_urls(db_path)


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
        lambda graph_db_path, api_key, items, boost_terms, top_n=20: [{**i, "_coarse_score": 0.9} for i in items],
    )
    monkeypatch.setattr("app.radar.pipeline.fetch_url", lambda url: "<html>full article body</html>")
    monkeypatch.setattr("app.radar.pipeline.extract_content", lambda html, url, data_root: "full article body")
    monkeypatch.setattr("app.radar.pipeline.judge_item", _judge_item)

    summary = refresh_radar(tmp_path, _StubProvider(), "fake-embed-key")

    assert summary["Misconfigured Source"]["error"] is not None
    assert summary["Misconfigured Source"]["new"] == 0
    assert summary["Good Source"]["error"] is None
    assert summary["Good Source"]["new"] == 1
