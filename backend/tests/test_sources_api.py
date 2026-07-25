from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_and_get_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    create_response = client.post("/sources", json={"title": "Test Note", "content": "Body"})
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["title"] == "Test Note"

    get_response = client.get(f"/sources/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["content"].strip() == "Body"


def test_list_sources(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    client.post("/sources", json={"title": "One", "content": "a"})
    client.post("/sources", json={"title": "Two", "content": "b"})

    response = client.get("/sources")
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()}
    assert titles == {"One", "Two"}


def test_get_missing_source_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.get("/sources/does-not-exist")
    assert response.status_code == 404
