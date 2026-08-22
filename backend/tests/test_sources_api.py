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


def test_create_source_pasting_same_text_twice_returns_existing_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    first = client.post("/sources", json={"title": "Note", "content": "Same body"}).json()
    second = client.post("/sources", json={"title": "Note again", "content": "Same body"}).json()

    assert second["id"] == first["id"]
    assert second["duplicate"] is True

    # No second directory should have been created under library/.
    assert len(list((tmp_path / "library").iterdir())) == 1


def test_create_source_from_url_twice_returns_existing_source_without_refetching(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    fetch_calls = {"n": 0}

    def _fetch(url):
        fetch_calls["n"] += 1
        return "<html><head><title>Fetched Title</title></head><body>hi</body></html>"

    monkeypatch.setattr("app.routers.sources.fetch_url", _fetch)
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Extracted body")

    first = client.post("/sources", json={"url": "https://example.com/article"}).json()
    second = client.post("/sources", json={"url": "https://example.com/article"}).json()

    assert second["id"] == first["id"]
    assert second["duplicate"] is True
    # The duplicate check runs before fetch_url, so a re-posted URL never
    # triggers a second fetch.
    assert fetch_calls["n"] == 1


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


def test_mark_source_read(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    created = client.post("/sources", json={"title": "T", "content": "c"}).json()
    assert created["read_at"] is None

    response = client.post(f"/sources/{created['id']}/read")
    assert response.status_code == 200
    assert response.json()["read_at"]

    # Idempotent: a second call returns the same read_at.
    second = client.post(f"/sources/{created['id']}/read")
    assert second.json()["read_at"] == response.json()["read_at"]

    # Reflected back in list/get.
    listed = client.get("/sources").json()
    assert listed[0]["read_at"] == response.json()["read_at"]
    fetched = client.get(f"/sources/{created['id']}").json()
    assert fetched["read_at"] == response.json()["read_at"]


def test_mark_missing_source_read_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/sources/does-not-exist/read")
    assert response.status_code == 404


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


def test_preview_triage_returns_duplicate_without_calling_extract_content(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "app.routers.sources.fetch_url",
        lambda url: "<html><head><title>Fetched Title</title></head><body>hi</body></html>",
    )
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Extracted body")
    saved = client.post("/sources", json={"url": "https://example.com/article"}).json()

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("extract_content should not be called for a duplicate URL")

    monkeypatch.setattr("app.routers.sources.extract_content", _fail_if_called)

    response = client.post(
        "/sources/preview-triage",
        json={"url": "https://example.com/article", "html": "<html>irrelevant</html>"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is True
    assert body["id"] == saved["id"]
    assert body["triage"] is None
    # No new library entries were created by the preview call.
    assert len(list((tmp_path / "library").iterdir())) == 1


def test_preview_triage_success_writes_nothing_to_disk(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Extracted body")
    monkeypatch.setattr(
        "app.routers.sources.run_triage",
        lambda state: {
            "triage": {
                "score": 72,
                "action": "worth_reading",
                "reason": "Clear and specific.",
                "read_time_minutes": 4,
                "density": 70,
                "originality": 65,
            },
            "triage_error": None,
        },
    )

    # The endpoint's actual promise is that NOTHING under data_root changes —
    # not just library/ — so snapshot the full recursive listing before and
    # after rather than checking one subdirectory. tmp_path may have no files
    # yet at all (only config.json written above), which this handles fine.
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

    response = client.post(
        "/sources/preview-triage",
        json={"url": "https://example.com/new-article", "html": "<html><body>Some content</body></html>"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is False
    assert body["triage"]["score"] == 72
    assert body["triage"]["action"] == "worth_reading"

    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert before == after


def test_preview_triage_extraction_provider_timeout_returns_504(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')

    def _raise_timeout(html, url, data_root):
        raise ProviderTimeoutError("provider timed out")

    monkeypatch.setattr("app.routers.sources.extract_content", _raise_timeout)

    response = client.post(
        "/sources/preview-triage",
        json={"url": "https://example.com/slow", "html": "<html><body>hi</body></html>"},
    )

    assert response.status_code == 504
    assert response.json()["error_type"] == "timeout"


def test_preview_triage_triage_failure_returns_502(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Extracted body")
    monkeypatch.setattr(
        "app.routers.sources.run_triage",
        lambda state: {"triage": None, "triage_error": "model returned invalid JSON"},
    )

    response = client.post(
        "/sources/preview-triage",
        json={"url": "https://example.com/bad-response", "html": "<html><body>hi</body></html>"},
    )

    assert response.status_code == 502
    assert response.json()["error_type"] == "error"


def test_preview_triage_missing_url_or_html_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/sources/preview-triage", json={"title": "No url or html"})

    assert response.status_code == 400
    body = response.json()
    assert body["error_type"] == "invalid"


def test_preview_triage_exercises_real_run_triage_against_a_fake_provider(tmp_path: Path, monkeypatch):
    """Every other preview-triage test monkeypatches run_triage itself, so the
    contract between the endpoint's hand-built AnalysisState dict and what
    run_triage actually reads from it (title/content/config/data_root) is
    never exercised. Here we patch one level lower — build_provider inside
    app.analysis.nodes — and let the real run_triage parse/validate a canned
    provider response via Triage.model_validate."""
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')
    monkeypatch.setattr("app.routers.sources.extract_content", lambda html, url, data_root: "Some plain content")

    class _FakeProvider:
        def complete(self, prompt):
            return (
                '{"score": 55, "action": "skim", "reason": "test", '
                '"read_time_minutes": 3, "density": 50, "originality": 50}'
            )

    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: _FakeProvider())

    response = client.post(
        "/sources/preview-triage",
        json={"url": "https://example.com/real-triage", "html": "<html><body>content</body></html>"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is False
    assert body["triage"]["score"] == 55
    assert body["triage"]["action"] == "skim"
