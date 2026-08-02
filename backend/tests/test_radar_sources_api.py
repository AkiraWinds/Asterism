import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_sources_returns_seeded_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.get("/radar/sources")

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) >= 1


def test_post_source_creates_new_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/radar/sources", json={"name": "My Blog", "url": "https://example.com/rss.xml"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "My Blog"
    assert body["enabled"] is True

    listed = client.get("/radar/sources").json()["sources"]
    assert any(s["name"] == "My Blog" for s in listed)


def test_patch_source_toggles_enabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    created = client.post("/radar/sources", json={"name": "X", "url": "https://x.com/rss"}).json()

    response = client.patch(f"/radar/sources/{created['id']}", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_delete_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    created = client.post("/radar/sources", json={"name": "X", "url": "https://x.com/rss"}).json()

    response = client.delete(f"/radar/sources/{created['id']}")

    assert response.status_code == 204
    listed = client.get("/radar/sources").json()["sources"]
    assert not any(s["id"] == created["id"] for s in listed)


def test_delete_source_404_on_missing_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.delete("/radar/sources/nonexistent-id")

    assert response.status_code == 404


def test_delete_boost_topic_404_on_missing_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.delete("/radar/boost-topics/nonexistent-id")

    assert response.status_code == 404


def test_boost_topics_crud(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    created = client.post("/radar/boost-topics", json={"term": "loop engineering"}).json()
    assert created["term"] == "loop engineering"

    listed = client.get("/radar/boost-topics").json()["topics"]
    assert any(t["term"] == "loop engineering" for t in listed)

    response = client.delete(f"/radar/boost-topics/{created['id']}")
    assert response.status_code == 204
