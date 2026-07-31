# backend/tests/test_highlights_api.py
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_source() -> str:
    response = client.post("/sources", json={"title": "Test", "content": "Some content."})
    return response.json()["id"]


def _write_config(data_root: Path) -> None:
    (data_root / "config.json").write_text(
        '{"strategy": "api-key", "provider": "anthropic", "api_key": "fake", "embeddings_api_key": "sk-embed"}'
    )


def _stub_extraction(monkeypatch, term="AI-first triage", definition="AI processes first."):
    provider = MagicMock()
    provider.complete.return_value = (
        f'[{{"term": "{term}", "definition": "{definition}", '
        '"self_relevant": false, "relationship": "none"}]'
    )
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])


def test_get_highlights_returns_empty_when_none_saved(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.get(f"/sources/{source_id}/highlights")

    assert response.status_code == 200
    assert response.json() == {"highlights": []}


def test_post_highlight_persists_and_creates_concept(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()
    _stub_extraction(monkeypatch)

    response = client.post(f"/sources/{source_id}/highlights", json={"source_quote": "the AI reads first"})

    assert response.status_code == 200
    body = response.json()
    assert body["highlight"]["source_quote"] == "the AI reads first"
    assert body["highlight"]["source_title"] == "Test"
    assert body["highlight"]["source_url"] is None
    assert len(body["concepts"]) == 1
    assert body["extraction_error"] is None

    history = client.get(f"/sources/{source_id}/highlights").json()
    assert history["highlights"][0]["source_quote"] == "the AI reads first"


def test_post_highlight_dedupes_identical_quote_and_note(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()
    _stub_extraction(monkeypatch)

    first = client.post(f"/sources/{source_id}/highlights", json={"source_quote": "the AI reads first"})
    second = client.post(f"/sources/{source_id}/highlights", json={"source_quote": "the AI reads first"})

    assert first.status_code == 200
    assert second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert first_body["duplicate"] is False
    assert second_body["duplicate"] is True
    assert second_body["highlight"]["id"] == first_body["highlight"]["id"]
    # No new extraction ran for the duplicate, so no second concept/edge was produced.
    assert second_body["concepts"] == []

    history = client.get(f"/sources/{source_id}/highlights").json()
    assert len(history["highlights"]) == 1


def test_post_highlight_same_quote_different_note_is_not_a_duplicate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()
    _stub_extraction(monkeypatch)

    client.post(f"/sources/{source_id}/highlights", json={"source_quote": "the AI reads first"})
    second = client.post(
        f"/sources/{source_id}/highlights",
        json={"source_quote": "the AI reads first", "note": "a distinct annotation"},
    )

    assert second.json()["duplicate"] is False
    history = client.get(f"/sources/{source_id}/highlights").json()
    assert len(history["highlights"]) == 2


def test_post_highlight_returns_404_for_unknown_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)

    response = client.post("/sources/does-not-exist/highlights", json={"source_quote": "q"})

    assert response.status_code == 404


def test_patch_highlight_updates_note_and_reruns_extraction(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()
    _stub_extraction(monkeypatch, term="AI-first triage")

    first_post = client.post(
        f"/sources/{source_id}/highlights", json={"source_quote": "the AI reads first"}
    ).json()
    highlight_id = first_post["highlight"]["id"]
    original_concept_id = first_post["concepts"][0]["id"]

    # Reprocessing after the note edit finds the concept from the first POST as a
    # nearest-neighbor (embed_text is stubbed to always return the same vector), which
    # triggers a second, dedup-shaped LLM call before the extraction-shaped one — so this
    # provider needs a two-step side_effect rather than the single-shape return_value
    # `_stub_extraction` uses (see the same pattern in test_concept_graph_pipeline.py for
    # scenarios where neighbors are already present in the graph). existing_concept_id
    # must resolve to a real concept row (pipeline.py's process_highlight rejects an
    # unknown id as a hallucinated dedup response), so it references the concept just
    # created by the first POST.
    provider = MagicMock()
    provider.complete.side_effect = [
        '[{"term": "AI-first triage, refined", "definition": "AI processes first.", '
        '"self_relevant": false, "relationship": "none"}]',
        f'[{{"existing_concept_id": "{original_concept_id}", "judgment": "new", '
        '"confidence": "high", "summary": "distinct concept"}]',
    ]
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])

    response = client.patch(
        f"/sources/{source_id}/highlights/{highlight_id}", json={"note": "a new note"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["highlight"]["note"] == "a new note"
    assert len(body["concepts"]) == 1
    assert body["concepts"][0]["term"] == "AI-first triage, refined"

    history = client.get(f"/sources/{source_id}/highlights").json()
    assert history["highlights"][0]["note"] == "a new note"


def test_patch_highlight_returns_404_for_unknown_highlight(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()

    response = client.patch(f"/sources/{source_id}/highlights/does-not-exist", json={"note": "x"})

    assert response.status_code == 404
