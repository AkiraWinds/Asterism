# backend/tests/test_graph_store.py
import sqlite3
from pathlib import Path

from app.graph_store.store import (
    delete_concept,
    delete_concept_highlights_for_highlight,
    delete_concept_sources_for_source,
    delete_review_queue_entry,
    get_concept,
    get_review_queue_entry,
    graph_db_path,
    init_db,
    insert_concept,
    insert_edge,
    insert_review_queue_entry,
    link_concept_highlight,
    link_concept_source,
    list_concepts,
    list_edges,
    list_review_queue,
    nearest_neighbors,
    repoint_concept_highlights,
    repoint_edges,
)


def _new_db(tmp_path: Path) -> Path:
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    return db_path


def test_insert_and_get_concept(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "Retrieval-augmented generation.", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    concept = get_concept(db_path, "c_1")
    assert concept["term"] == "RAG"
    assert concept["self_relevant"] == 0


def test_list_concepts_returns_all(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def1", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "GraphRAG", "def2", [0.2], False, "2026-07-30T00:00:01Z")
    assert {c["id"] for c in list_concepts(db_path)} == {"c_1", "c_2"}


def test_delete_concept_removes_row(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    delete_concept(db_path, "c_1")
    assert get_concept(db_path, "c_1") is None


def test_link_and_repoint_concept_highlights(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "GraphRAG", "def", [0.2], False, "2026-07-30T00:00:01Z")
    link_concept_highlight(db_path, "c_1", "source_a", "h_1")

    repoint_concept_highlights(db_path, "c_1", "c_2")

    import sqlite3
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT concept_id FROM concept_highlights WHERE highlight_id = ?", ("h_1",)).fetchall()
    conn.close()
    assert rows == [("c_2",)]


def test_delete_concept_highlights_for_highlight_clears_only_that_highlights_links(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    link_concept_highlight(db_path, "c_1", "source_a", "h_1")
    link_concept_highlight(db_path, "c_1", "source_a", "h_2")

    delete_concept_highlights_for_highlight(db_path, "h_1")

    import sqlite3
    conn = sqlite3.connect(db_path)
    remaining = conn.execute("SELECT highlight_id FROM concept_highlights").fetchall()
    conn.close()
    assert remaining == [("h_2",)]


def test_insert_and_list_edges(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "GraphRAG", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_edge(db_path, "e_1", "c_1", "c_2", "related", "both about retrieval")

    edges = list_edges(db_path)
    assert len(edges) == 1
    assert edges[0]["type"] == "related"


def test_repoint_edges_retargets_from_and_to_ids(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "GraphRAG", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_concept(db_path, "c_3", "Vector search", "def", [0.3], False, "2026-07-30T00:00:02Z")
    insert_edge(db_path, "e_from", "c_2", "c_3", "related", "c_2 references c_3")
    insert_edge(db_path, "e_to", "c_3", "c_2", "related", "c_3 references c_2")

    repoint_edges(db_path, "c_2", "c_1")

    edges = {e["id"]: e for e in list_edges(db_path)}
    assert edges["e_from"]["from_id"] == "c_1"
    assert edges["e_from"]["to_id"] == "c_3"
    assert edges["e_to"]["from_id"] == "c_3"
    assert edges["e_to"]["to_id"] == "c_1"


def test_review_queue_insert_list_get_delete(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_2", "GraphRAG", "def", [0.2], False, "2026-07-30T00:00:01Z")
    insert_review_queue_entry(db_path, "rq_1", "c_2", "c_1", "related, not same", "2026-07-30T00:00:02Z")

    entries = list_review_queue(db_path)
    assert len(entries) == 1
    assert get_review_queue_entry(db_path, "rq_1")["llm_judgment"] == "related, not same"

    delete_review_queue_entry(db_path, "rq_1")
    assert get_review_queue_entry(db_path, "rq_1") is None


def test_init_db_migrates_review_queue_missing_proposed_edge_type_column(tmp_path: Path):
    # Simulates a graph.db created before this column existed (Phase 6b).
    # CREATE TABLE IF NOT EXISTS alone cannot add a column to a table that
    # already exists on disk — init_db must migrate it.
    db_path = tmp_path / "graph.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE review_queue (id TEXT PRIMARY KEY, candidate_concept_id TEXT NOT NULL, "
        "existing_concept_id TEXT NOT NULL, llm_judgment TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO review_queue VALUES ('rq_old', 'c_1', 'c_2', 'old row', '2026-07-30T00:00:00Z')"
    )
    conn.commit()
    conn.close()

    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cols = {row[1] for row in conn.execute("PRAGMA table_info(review_queue)")}
        assert "proposed_edge_type" in cols
        row = conn.execute("SELECT proposed_edge_type FROM review_queue WHERE id = 'rq_old'").fetchone()
        assert row["proposed_edge_type"] == "related"


def test_nearest_neighbors_ranks_by_cosine_similarity(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_close", "A", "def", [1.0, 0.0], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_far", "B", "def", [0.0, 1.0], False, "2026-07-30T00:00:01Z")

    results = nearest_neighbors(db_path, [1.0, 0.01], top_k=2)

    assert results[0][0]["id"] == "c_close"
    assert results[0][1] > results[1][1]


def test_link_concept_source_creates_provenance_row(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")

    link_concept_source(db_path, "c_1", "source_a")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT concept_id, source_id FROM concept_sources").fetchall()
    assert [(r["concept_id"], r["source_id"]) for r in rows] == [("c_1", "source_a")]


def test_delete_concept_sources_for_source_clears_only_that_sources_links(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    link_concept_source(db_path, "c_1", "source_a")
    link_concept_source(db_path, "c_1", "source_b")

    delete_concept_sources_for_source(db_path, "source_a")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        remaining = conn.execute("SELECT source_id FROM concept_sources").fetchall()
    assert [r["source_id"] for r in remaining] == ["source_b"]
