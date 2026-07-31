import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.graph_store.store import graph_db_path, init_db, insert_concept, link_concept_highlight
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
