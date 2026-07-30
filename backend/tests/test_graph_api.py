# backend/tests/test_graph_api.py
from pathlib import Path

from fastapi.testclient import TestClient

from app.graph_store.store import (
    get_concept,
    graph_db_path,
    init_db,
    insert_concept,
    insert_review_queue_entry,
    link_concept_highlight,
    list_review_queue,
)
from app.main import app

client = TestClient(app)


def test_get_graph_returns_empty_when_no_db_yet(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    response = client.get("/graph")
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}


def test_get_graph_returns_concepts_and_edges(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")

    response = client.get("/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"][0]["id"] == "c_1"


def test_get_review_queue_lists_pending_entries(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_review_queue_entry(db_path, "rq_1", "c_2", "c_1", "related but distinct", "2026-07-30T00:00:02Z")

    response = client.get("/graph/review-queue")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "rq_1"


def test_resolve_merge_repoints_highlights_and_deletes_candidate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-07-30T00:00:01Z")
    link_concept_highlight(db_path, "c_2", "source_a", "h_1")
    insert_review_queue_entry(db_path, "rq_1", "c_2", "c_1", "related but distinct", "2026-07-30T00:00:02Z")

    response = client.post("/graph/review-queue/rq_1/resolve", json={"action": "merge"})

    assert response.status_code == 200
    assert get_concept(db_path, "c_2") is None
    assert list_review_queue(db_path) == []


def test_resolve_keep_separate_creates_edge_and_clears_queue(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_review_queue_entry(db_path, "rq_1", "c_2", "c_1", "related but distinct", "2026-07-30T00:00:02Z")

    response = client.post("/graph/review-queue/rq_1/resolve", json={"action": "keep_separate"})

    assert response.status_code == 200
    graph = client.get("/graph").json()
    assert len(graph["edges"]) == 1
    assert list_review_queue(db_path) == []


def test_resolve_returns_404_for_unknown_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    response = client.post("/graph/review-queue/does-not-exist/resolve", json={"action": "merge"})

    assert response.status_code == 404
