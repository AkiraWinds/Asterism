# backend/tests/test_graph_api.py
from pathlib import Path

from fastapi.testclient import TestClient

from app.graph_store.store import (
    get_concept,
    graph_db_path,
    init_db,
    insert_concept,
    insert_edge,
    insert_review_queue_entry,
    link_concept_highlight,
    list_edges,
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


def test_resolve_merge_repoints_edges_touching_the_deleted_candidate(tmp_path: Path, monkeypatch):
    # Regression test for a dangling-edge bug: merging used to repoint
    # concept_highlights and delete the candidate concept, but left any
    # `edges` row referencing the candidate as-is — once the candidate row was
    # gone, GET /graph would return an edge pointing at a nonexistent node,
    # which crashes react-force-graph-2d client-side. Edges touching the
    # candidate (in either direction) must be repointed at the surviving
    # concept instead.
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_concept(db_path, "c_3", "C", "def", [0.3], False, "2026-07-30T00:00:02Z")
    # c_2 is the merge candidate; c_1 is the surviving/existing concept.
    insert_edge(db_path, "e_1", "c_2", "c_3", "related", "candidate references c_3")
    insert_review_queue_entry(db_path, "rq_1", "c_2", "c_1", "related but distinct", "2026-07-30T00:00:02Z")

    response = client.post("/graph/review-queue/rq_1/resolve", json={"action": "merge"})

    assert response.status_code == 200
    assert get_concept(db_path, "c_2") is None
    stored_edges = {e["id"]: e for e in list_edges(db_path)}
    assert stored_edges["e_1"]["from_id"] == "c_1"
    assert stored_edges["e_1"]["to_id"] == "c_3"

    # GET /graph must not surface any edge pointing at a deleted node.
    graph = client.get("/graph").json()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert all(e["from_id"] in node_ids and e["to_id"] in node_ids for e in graph["edges"])


def test_get_graph_filters_out_edges_with_dangling_endpoints(tmp_path: Path, monkeypatch):
    # Defensive filter: even if some other path produced a dangling edge,
    # GET /graph must not return it, since react-force-graph-2d crashes on an
    # edge referencing a node id that isn't in the returned node set.
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_edge(db_path, "e_dangling", "c_1", "c_missing", "related", "dangling")

    response = client.get("/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["edges"] == []


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


def test_resolve_keep_separate_uses_stored_proposed_edge_type(tmp_path: Path, monkeypatch):
    # resolve_review_queue_endpoint's "keep_separate" branch used to hardcode
    # insert_edge(..., "related", ...) regardless of what was actually
    # classified — this must use the entry's own proposed_edge_type instead,
    # otherwise approving a queued "contradicts" entry would silently create
    # a "related" edge and defeat the whole point of force-queuing it.
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_review_queue_entry(
        db_path, "rq_1", "c_2", "c_1", "these conflict", "2026-07-30T00:00:02Z",
        proposed_edge_type="contradicts",
    )

    response = client.post("/graph/review-queue/rq_1/resolve", json={"action": "keep_separate"})

    assert response.status_code == 200
    graph = client.get("/graph").json()
    assert graph["edges"][0]["type"] == "contradicts"


def test_resolve_returns_404_for_unknown_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    response = client.post("/graph/review-queue/does-not-exist/resolve", json={"action": "merge"})

    assert response.status_code == 404
