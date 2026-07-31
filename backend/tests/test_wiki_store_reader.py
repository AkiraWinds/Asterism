import sqlite3
from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, insert_edge, link_concept_highlight
from app.wiki.store_reader import get_concept_provenance, get_edges_for_concept


def _new_db(tmp_path: Path) -> Path:
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    return db_path


def test_get_concept_provenance_reads_highlight_rows(tmp_path: Path):
    db_path = _new_db(tmp_path)
    link_concept_highlight(db_path, "c_1", "s_a", "h_1")
    link_concept_highlight(db_path, "c_1", "s_b", "h_2")

    provenance = get_concept_provenance(db_path, "c_1")

    assert sorted(provenance, key=lambda p: p["source_id"]) == [
        {"source_id": "s_a", "highlight_id": "h_1"},
        {"source_id": "s_b", "highlight_id": "h_2"},
    ]


def test_get_concept_provenance_unions_concept_sources_when_present(tmp_path: Path):
    db_path = _new_db(tmp_path)
    link_concept_highlight(db_path, "c_1", "s_a", "h_1")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE concept_sources (concept_id TEXT, source_id TEXT)")
    conn.execute("INSERT INTO concept_sources (concept_id, source_id) VALUES ('c_1', 's_c')")
    conn.commit()
    conn.close()

    provenance = get_concept_provenance(db_path, "c_1")

    assert {"source_id": "s_c", "highlight_id": None} in provenance
    assert {"source_id": "s_a", "highlight_id": "h_1"} in provenance


def test_get_concept_provenance_tolerates_missing_concept_sources_table(tmp_path: Path):
    db_path = _new_db(tmp_path)
    link_concept_highlight(db_path, "c_1", "s_a", "h_1")

    provenance = get_concept_provenance(db_path, "c_1")

    assert provenance == [{"source_id": "s_a", "highlight_id": "h_1"}]


def test_get_edges_for_concept_filters_by_endpoint(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_edge(db_path, "e_1", "c_1", "c_2", "related", "summary a")
    insert_edge(db_path, "e_2", "c_3", "c_4", "related", "summary b")

    edges = get_edges_for_concept(db_path, "c_1")

    assert [e["id"] for e in edges] == ["e_1"]
