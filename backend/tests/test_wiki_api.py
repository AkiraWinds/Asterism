import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.graph_store.store import graph_db_path, init_db
from app.main import app

client = TestClient(app)


def _write_config(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({
        "strategy": "api-key", "provider": "anthropic", "api_key": "test-key",
    }))


def test_post_wiki_compile_returns_400_without_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    response = client.post("/wiki/compile")
    assert response.status_code == 400


def test_post_wiki_compile_returns_summary_with_no_qualifying_concepts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    response = client.post("/wiki/compile")

    assert response.status_code == 200
    assert response.json() == {"pages_updated": 0, "pages_new": 0, "orphans_flagged": 0, "errors": []}


def _write_overview_page(data_root: Path, slug: str, concept_id: str, term: str) -> None:
    wiki_dir = data_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / f"{slug}.md").write_text(
        f'---\nconcept_id: {json.dumps(concept_id)}\nterm: {json.dumps(term)}\n'
        f'updated_at: "2026-08-01T00:00:00Z"\nsource_highlight_count: 3\n'
        f'source_provenance_hash: "abc"\nsource_ids: []\n---\n\nBody text.\n'
    )


def test_get_wiki_page_by_concept_id_returns_200(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_overview_page(tmp_path, "rag", "c_1", "RAG")

    response = client.get("/wiki/pages/c_1")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "rag"
    assert body["term"] == "RAG"
    assert "Body text." in body["body"]
    assert body["aspects"] == []


def test_get_wiki_page_by_concept_id_returns_404_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.get("/wiki/pages/c_missing")

    assert response.status_code == 404


def test_get_wiki_page_by_slug_returns_200(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_overview_page(tmp_path, "rag", "c_1", "RAG")

    response = client.get("/wiki/pages/by-slug/rag")

    assert response.status_code == 200
    assert response.json()["term"] == "RAG"


def test_get_wiki_page_by_slug_returns_404_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.get("/wiki/pages/by-slug/nonexistent")

    assert response.status_code == 404
