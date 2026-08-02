# backend/tests/test_graph_store.py
import sqlite3
from pathlib import Path

import pytest

from app.graph_store.store import (
    delete_concept,
    delete_concept_highlights_for_highlight,
    delete_concept_sources_for_source,
    delete_review_queue_entry,
    delete_watchlist_entry,
    get_concept,
    get_review_queue_entry,
    get_watchlist_entry,
    graph_db_path,
    init_db,
    insert_concept,
    insert_edge,
    insert_review_queue_entry,
    insert_watchlist_entry,
    link_concept_highlight,
    link_concept_source,
    list_concepts,
    list_edges,
    list_review_queue,
    list_watchlist_entries,
    nearest_neighbors,
    repoint_concept_highlights,
    repoint_edges,
    set_concept_golden,
    update_watchlist_entry,
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


def test_insert_concept_defaults_golden_false(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    assert get_concept(db_path, "c_1")["golden"] is False


def test_insert_concept_accepts_golden_true(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z", golden=True)
    assert get_concept(db_path, "c_1")["golden"] is True


def test_set_concept_golden_updates_existing_row(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    set_concept_golden(db_path, "c_1", True)
    assert get_concept(db_path, "c_1")["golden"] is True


def test_init_db_migrates_existing_concepts_table_without_golden_column(tmp_path: Path):
    # Simulate a pre-migration graph.db: create the table by hand without `golden`.
    db_path = graph_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE concepts (id TEXT PRIMARY KEY, term TEXT NOT NULL, definition TEXT NOT NULL, "
        "embedding TEXT NOT NULL, self_relevant INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    init_db(db_path)  # must not raise, and must add the column

    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-30T00:00:00Z")
    assert get_concept(db_path, "c_1")["golden"] is False


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
    # [1] is true_similarity, [2] is the golden-boosted ranking score.
    assert results[0][1] > results[1][1]
    assert results[0][2] > results[1][2]


def test_nearest_neighbors_ranks_golden_above_similar_non_golden(tmp_path: Path):
    db_path = _new_db(tmp_path)
    # Two concepts with near-identical embeddings; only c_2 is golden.
    insert_concept(db_path, "c_1", "A", "def1", [1.0, 0.0], False, "2026-08-01T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def2", [0.99, 0.01], False, "2026-08-01T00:00:01Z", golden=True)

    results = nearest_neighbors(db_path, [1.0, 0.0], top_k=2)

    assert results[0][0]["id"] == "c_2"


def test_nearest_neighbors_true_similarity_gap_beats_golden_bonus(tmp_path: Path):
    db_path = _new_db(tmp_path)
    # c_1 is a near-perfect match and non-golden; c_2 is golden but nearly orthogonal.
    insert_concept(db_path, "c_1", "A", "def1", [1.0, 0.0], False, "2026-08-01T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def2", [0.0, 1.0], False, "2026-08-01T00:00:01Z", golden=True)

    results = nearest_neighbors(db_path, [1.0, 0.0], top_k=2)

    assert results[0][0]["id"] == "c_1"


def test_nearest_neighbors_true_similarity_excludes_golden_bonus(tmp_path: Path):
    # Whole-branch review finding #3: nearest_neighbors must expose the
    # UNBOOSTED cosine similarity (index [1]) separately from the ranking
    # score (index [2]) so callers doing an absolute-threshold comparison
    # (e.g. the watchlist resolver) don't have the golden tie-breaker bonus
    # leak into that threshold.
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_golden", "A", "def1", [1.0, 0.0], False, "2026-08-01T00:00:00Z", golden=True)

    results = nearest_neighbors(db_path, [1.0, 0.0], top_k=1)

    concept, true_similarity, boosted_score = results[0]
    assert concept["id"] == "c_golden"
    assert true_similarity == pytest.approx(1.0)
    assert boosted_score == pytest.approx(1.0 + 0.05)
    assert boosted_score != true_similarity


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


def test_insert_watchlist_entry_defaults_to_pending(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")
    entry = get_watchlist_entry(db_path, "w_1")
    assert entry["term"] == "Agentic AI"
    assert entry["status"] == "pending"
    assert entry["draft_definition"] is None
    assert entry["draft_matched_concept_id"] is None
    assert entry["resolved_concept_id"] is None


def test_list_watchlist_entries_returns_all(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")
    insert_watchlist_entry(db_path, "w_2", "Multi-agent systems", "2026-08-01T00:00:01Z")
    assert {e["id"] for e in list_watchlist_entries(db_path)} == {"w_1", "w_2"}


def test_list_watchlist_entries_orders_most_recently_updated_first(tmp_path: Path):
    # Docstring claims "most recently updated first" — the query previously
    # had no ORDER BY, so that was only true by accident of insertion order.
    db_path = _new_db(tmp_path)
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")
    insert_watchlist_entry(db_path, "w_2", "Multi-agent systems", "2026-08-01T00:00:01Z")
    # Touch w_1 after w_2 was created, so it should now sort first.
    update_watchlist_entry(db_path, "w_1", status="rejected", updated_at="2026-08-01T00:00:02Z")

    result = list_watchlist_entries(db_path)

    assert [e["id"] for e in result] == ["w_1", "w_2"]


def test_update_watchlist_entry_sets_fields_and_bumps_updated_at(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")

    update_watchlist_entry(db_path, "w_1", status="resolved", resolved_concept_id="c_1", updated_at="2026-08-01T01:00:00Z")

    entry = get_watchlist_entry(db_path, "w_1")
    assert entry["status"] == "resolved"
    assert entry["resolved_concept_id"] == "c_1"
    assert entry["updated_at"] == "2026-08-01T01:00:00Z"


def test_delete_watchlist_entry_removes_row(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")
    delete_watchlist_entry(db_path, "w_1")
    assert get_watchlist_entry(db_path, "w_1") is None


def test_delete_watchlist_entry_does_not_delete_resolved_concept(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "Agentic AI", "def", [0.1], False, "2026-08-01T00:00:00Z", golden=True)
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")
    update_watchlist_entry(db_path, "w_1", status="resolved", resolved_concept_id="c_1", updated_at="2026-08-01T00:00:01Z")

    delete_watchlist_entry(db_path, "w_1")

    assert get_concept(db_path, "c_1") is not None
