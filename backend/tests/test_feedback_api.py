# backend/tests/test_feedback_api.py
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


def test_get_feedback_returns_empty_when_none_saved(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.get(f"/sources/{source_id}/feedback")

    assert response.status_code == 200
    assert response.json() == {"entries": []}


def test_put_feedback_creates_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "claim", "content": "The sky is blue.", "rating": "up"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "claim"
    assert body["rating"] == "up"
    assert body["promoted"] is False


def test_put_feedback_requires_section_for_critique(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "critique", "content": "Assumes X.", "rating": "up"},
    )

    assert response.status_code == 422


def test_put_feedback_requires_term_for_concept(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "concept", "content": "def", "rating": "up"},
    )

    assert response.status_code == 422


def test_put_feedback_rejects_term_for_non_concept(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "claim", "content": "The sky is blue.", "term": "stray", "rating": "up"},
    )

    assert response.status_code == 422


def test_promote_claim_creates_highlight_and_marks_promoted(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()

    provider = MagicMock()
    provider.complete.return_value = '[{"term": "t", "definition": "The sky is blue.", "self_relevant": false}]'
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])

    rate_response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "claim", "content": "The sky is blue.", "rating": "up"},
    )
    feedback_id = rate_response.json()["id"]

    response = client.post(f"/sources/{source_id}/feedback/{feedback_id}/promote")

    assert response.status_code == 200
    body = response.json()
    assert body["highlight"]["source_quote"] == "The sky is blue."
    assert len(body["concepts"]) == 1

    feedback = client.get(f"/sources/{source_id}/feedback").json()["entries"][0]
    assert feedback["promoted"] is True
    assert feedback["promoted_at"] is not None

    highlights = client.get(f"/sources/{source_id}/highlights").json()["highlights"]
    assert len(highlights) == 1
    assert highlights[0]["source_quote"] == "The sky is blue."


def test_promote_concept_uses_promote_concept_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()

    provider = MagicMock()
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])

    rate_response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "concept", "content": "AI processes fast.", "term": "AI-first", "rating": "up"},
    )
    feedback_id = rate_response.json()["id"]

    response = client.post(f"/sources/{source_id}/feedback/{feedback_id}/promote")

    assert response.status_code == 200
    assert len(response.json()["concepts"]) == 1
    provider.complete.assert_not_called()  # promote_concept skips extraction — no LLM call expected


def test_promote_returns_400_when_not_upvoted(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()

    rate_response = client.put(
        f"/sources/{source_id}/feedback",
        json={"kind": "claim", "content": "text", "rating": "down"},
    )
    feedback_id = rate_response.json()["id"]

    response = client.post(f"/sources/{source_id}/feedback/{feedback_id}/promote")

    assert response.status_code == 400


def test_promote_returns_400_when_already_promoted(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    source_id = _create_source()

    provider = MagicMock()
    provider.complete.return_value = '[{"term": "t", "definition": "d", "self_relevant": false}]'
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])

    rate_response = client.put(
        f"/sources/{source_id}/feedback", json={"kind": "claim", "content": "text", "rating": "up"}
    )
    feedback_id = rate_response.json()["id"]
    client.post(f"/sources/{source_id}/feedback/{feedback_id}/promote")

    response = client.post(f"/sources/{source_id}/feedback/{feedback_id}/promote")

    assert response.status_code == 400


def test_promote_returns_404_for_unknown_feedback_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.post(f"/sources/{source_id}/feedback/does-not-exist/promote")

    assert response.status_code == 404


def test_promote_sets_promoted_true_even_on_config_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()  # no config.json written — _load_llm_and_embeddings raises ConfigError

    rate_response = client.put(
        f"/sources/{source_id}/feedback", json={"kind": "claim", "content": "text", "rating": "up"}
    )
    feedback_id = rate_response.json()["id"]

    response = client.post(f"/sources/{source_id}/feedback/{feedback_id}/promote")

    assert response.status_code == 200
    assert response.json()["extraction_error"] is not None
    feedback = client.get(f"/sources/{source_id}/feedback").json()["entries"][0]
    assert feedback["promoted"] is True
