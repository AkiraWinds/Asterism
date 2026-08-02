from pathlib import Path

from app.radar_store.store import (
    get_radar_item,
    init_db,
    insert_boost_topic,
    insert_radar_item,
    list_all_radar_item_urls,
    list_boost_topics,
    list_new_radar_items,
    radar_db_path,
    update_radar_item_status,
)


def test_boost_topic_crud(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)

    insert_boost_topic(db_path, "b1", "loop engineering", "2026-08-02T00:00:00+00:00")
    topics = list_boost_topics(db_path)
    assert len(topics) == 1
    assert topics[0]["term"] == "loop engineering"


def test_insert_radar_item_dedupes_by_url(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)

    kwargs = dict(
        item_id="i1", source_id="seed_0", url="https://example.com/a", title="A", summary="summary",
        published_at=None, relevance_score=0.8, quality_score=0.6, reasoning="matches interests",
        created_at="2026-08-02T00:00:00+00:00",
    )
    assert insert_radar_item(db_path, **kwargs) is True
    # Same URL again (e.g. a later run re-fetches the same item) — must not duplicate.
    kwargs["item_id"] = "i2"
    assert insert_radar_item(db_path, **kwargs) is False

    assert list_all_radar_item_urls(db_path) == {"https://example.com/a"}


def test_list_new_radar_items_orders_by_relevance_and_respects_cutoff(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)

    insert_radar_item(
        db_path, item_id="old", source_id="seed_0", url="https://example.com/old", title="Old", summary="s",
        published_at=None, relevance_score=0.9, quality_score=0.5, reasoning="r",
        created_at="2026-01-01T00:00:00+00:00",
    )
    insert_radar_item(
        db_path, item_id="low", source_id="seed_0", url="https://example.com/low", title="Low", summary="s",
        published_at=None, relevance_score=0.3, quality_score=0.5, reasoning="r",
        created_at="2026-08-02T00:00:00+00:00",
    )
    insert_radar_item(
        db_path, item_id="high", source_id="seed_0", url="https://example.com/high", title="High", summary="s",
        published_at=None, relevance_score=0.95, quality_score=0.5, reasoning="r",
        created_at="2026-08-02T00:00:00+00:00",
    )

    items = list_new_radar_items(db_path, cutoff_iso="2026-07-01T00:00:00+00:00")
    assert [i["id"] for i in items] == ["high", "low"]  # "old" excluded by cutoff, rest ranked by relevance desc


def test_update_radar_item_status(tmp_path: Path):
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    insert_radar_item(
        db_path, item_id="i1", source_id="seed_0", url="https://example.com/a", title="A", summary="s",
        published_at=None, relevance_score=0.8, quality_score=0.6, reasoning="r",
        created_at="2026-08-02T00:00:00+00:00",
    )

    update_radar_item_status(db_path, "i1", status="added", added_source_id="src123")

    item = get_radar_item(db_path, "i1")
    assert item["status"] == "added"
    assert item["added_source_id"] == "src123"
