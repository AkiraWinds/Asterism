from pathlib import Path

from app.radar_store.store import (
    delete_feed_source,
    get_feed_source,
    init_db,
    insert_feed_source,
    list_feed_sources,
    radar_db_path,
    update_feed_source,
    update_feed_source_fetch_status,
)


def test_init_db_seeds_default_sources(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)

    sources = list_feed_sources(db_path)
    assert len(sources) >= 1
    assert all(s["enabled"] for s in sources)
    assert all(s["last_fetch_status"] is None for s in sources)


def test_init_db_is_idempotent_and_does_not_reseed(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    first_count = len(list_feed_sources(db_path))
    init_db(db_path)
    assert len(list_feed_sources(db_path)) == first_count


def test_insert_get_update_delete_feed_source(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)

    insert_feed_source(db_path, "s1", "Test Blog", "https://example.com/rss.xml", "2026-08-02T00:00:00+00:00")

    fetched = get_feed_source(db_path, "s1")
    assert fetched["name"] == "Test Blog"
    assert fetched["url"] == "https://example.com/rss.xml"
    assert fetched["enabled"] is True

    update_feed_source(db_path, "s1", name="Renamed Blog", enabled=False)
    fetched = get_feed_source(db_path, "s1")
    assert fetched["name"] == "Renamed Blog"
    assert fetched["enabled"] is False

    update_feed_source_fetch_status(db_path, "s1", status="error", error="timeout", fetched_at="2026-08-02T01:00:00+00:00")
    fetched = get_feed_source(db_path, "s1")
    assert fetched["last_fetch_status"] == "error"
    assert fetched["last_fetch_error"] == "timeout"
    assert fetched["last_fetched_at"] == "2026-08-02T01:00:00+00:00"

    delete_feed_source(db_path, "s1")
    assert get_feed_source(db_path, "s1") is None
