from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import ProviderError, ProviderTimeoutError
from app.repositories.config_repository import ConfigError

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


def test_delete_source_removes_it(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    created = client.post("/sources", json={"title": "To Delete", "content": "Body"}).json()

    delete_response = client.delete(f"/sources/{created['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/sources/{created['id']}")
    assert get_response.status_code == 404


def test_delete_missing_source_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.delete("/sources/does-not-exist")
    assert response.status_code == 404


def test_create_source_from_url_success(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "app.routers.sources.fetch_url",
        lambda url: "<html><head><title>Fetched Title</title></head><body>hi</body></html>",
    )
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Extracted body")

    response = client.post("/sources", json={"url": "https://example.com/article"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Fetched Title"
    assert body["content"].strip() == "Extracted body"


def test_create_source_from_url_login_required_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/sources", json={"url": "https://x.com/someone/status/1"})

    assert response.status_code == 400
    assert response.json()["error_type"] == "login_required"


def test_create_source_from_url_extraction_provider_timeout_returns_504(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "app.routers.sources.fetch_url",
        lambda url: "<html><head><title>T</title></head><body>hi</body></html>",
    )

    def _raise_timeout(html, url, data_root):
        raise ProviderTimeoutError("provider timed out")

    monkeypatch.setattr("app.routers.sources.extract_content", _raise_timeout)

    response = client.post("/sources", json={"url": "https://example.com/slow"})

    assert response.status_code == 504
    assert response.json()["error_type"] == "timeout"


def test_create_source_missing_title_or_content_without_url_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/sources", json={"title": "Only Title"})

    assert response.status_code == 400


def test_create_source_from_url_extraction_config_error_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "app.routers.sources.fetch_url",
        lambda url: "<html><head><title>T</title></head><body>hi</body></html>",
    )

    def _raise_config_error(html, url, data_root):
        raise ConfigError("bad config")

    monkeypatch.setattr("app.routers.sources.extract_content", _raise_config_error)

    response = client.post("/sources", json={"url": "https://example.com/bad-config"})

    assert response.status_code == 400
    assert response.json()["error_type"] == "config"


def test_create_source_with_prefetched_html_skips_fetch_url(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    def _unexpected_fetch(url):
        raise AssertionError("fetch_url should not be called when html is supplied")

    monkeypatch.setattr("app.routers.sources.fetch_url", _unexpected_fetch)
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Extracted body")

    response = client.post(
        "/sources",
        json={
            "url": "https://example.com/member-article",
            "title": "Ignored — extension-supplied title is not used for meta.original_title",
            "html": "<html><head><title>Captured Title</title></head><body>member content</body></html>",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Captured Title"
    assert body["content"].strip() == "Extracted body"
