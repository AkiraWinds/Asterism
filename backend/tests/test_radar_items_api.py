import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.radar_store.store import init_db, insert_radar_item, radar_db_path

client = TestClient(app)


def _write_config(data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "config.json").write_text(json.dumps({
        "strategy": "api-key", "provider": "openai", "api_key": "fake", "embeddings_api_key": "fake-embed",
    }))


def test_get_radar_excludes_expired_items(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = radar_db_path(tmp_path)
    init_db(db_path)

    old_created_at = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    insert_radar_item(
        db_path, item_id="old", source_id="seed_0", url="https://example.com/old", title="Old", summary="s",
        published_at=None, relevance_score=0.9, quality_score=0.5, reasoning="r", created_at=old_created_at,
    )
    insert_radar_item(
        db_path, item_id="fresh", source_id="seed_0", url="https://example.com/fresh", title="Fresh", summary="s",
        published_at=None, relevance_score=0.8, quality_score=0.5, reasoning="r",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    response = client.get("/radar")

    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert ids == ["fresh"]


def test_dismiss_item_marks_status(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    insert_radar_item(
        db_path, item_id="i1", source_id="seed_0", url="https://example.com/a", title="A", summary="s",
        published_at=None, relevance_score=0.8, quality_score=0.5, reasoning="r",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    response = client.post("/radar/items/i1/dismiss")

    assert response.status_code == 204
    assert client.get("/radar").json()["items"] == []


def test_add_item_creates_library_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    insert_radar_item(
        db_path, item_id="i1", source_id="seed_0", url="https://example.com/a", title="A", summary="s",
        published_at=None, relevance_score=0.8, quality_score=0.5, reasoning="r",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    monkeypatch.setattr("app.routers.radar.fetch_url", lambda url: "<html><title>A</title>full body</html>")
    monkeypatch.setattr("app.routers.radar.extract_content", lambda html, url, data_root: "full body")

    response = client.post("/radar/items/i1/add")

    assert response.status_code == 200
    assert client.get("/radar").json()["items"] == []  # no longer 'new'


def test_dismiss_already_added_item_returns_409(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    insert_radar_item(
        db_path, item_id="i1", source_id="seed_0", url="https://example.com/a", title="A", summary="s",
        published_at=None, relevance_score=0.8, quality_score=0.5, reasoning="r",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    monkeypatch.setattr("app.routers.radar.fetch_url", lambda url: "<html><title>A</title>full body</html>")
    monkeypatch.setattr("app.routers.radar.extract_content", lambda html, url, data_root: "full body")

    add_response = client.post("/radar/items/i1/add")
    assert add_response.status_code == 200
    added_source_id = add_response.json()["id"]

    dismiss_response = client.post("/radar/items/i1/dismiss")

    assert dismiss_response.status_code == 409

    # The link to the library source it was added as must survive the
    # rejected dismiss attempt.
    from app.radar_store.store import get_radar_item

    item = get_radar_item(db_path, "i1")
    assert item["status"] == "added"
    assert item["added_source_id"] == added_source_id


def test_refresh_endpoint_invokes_pipeline(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.radar.refresh_radar", lambda data_root, provider, api_key: {"Some Source": {"fetched": 2, "new": 1, "error": None}})

    response = client.post("/radar/refresh")

    assert response.status_code == 200
    assert response.json()["per_source"]["Some Source"]["new"] == 1


def test_refresh_endpoint_returns_400_on_config_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    # No config.json written — load_config should raise ConfigError.

    response = client.post("/radar/refresh")

    assert response.status_code == 400


def test_add_item_returns_502_on_fetch_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    db_path = radar_db_path(tmp_path)
    init_db(db_path)
    insert_radar_item(
        db_path, item_id="i1", source_id="seed_0", url="https://example.com/a", title="A", summary="s",
        published_at=None, relevance_score=0.8, quality_score=0.5, reasoning="r",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    from app.ingestion.fetcher import FetchError

    def _raise_fetch_error(url):
        raise FetchError("boom")

    monkeypatch.setattr("app.routers.radar.fetch_url", _raise_fetch_error)

    response = client.post("/radar/items/i1/add")

    assert response.status_code == 502
    assert "detail" in response.json()

    # Item must remain 'new' and safely retryable, not corrupted.
    ids = [i["id"] for i in client.get("/radar").json()["items"]]
    assert ids == ["i1"]
