from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, insert_concept, insert_edge
from app.graph_store.view import build_graph_response


def _new_db(tmp_path: Path) -> Path:
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    return db_path


def test_build_graph_response_includes_concept_nodes(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-09-10T00:00:00Z", golden=True)

    response = build_graph_response(tmp_path, db_path)

    assert len(response.nodes) == 1
    node = response.nodes[0]
    assert node.id == "c_1" and node.kind == "concept" and node.term == "RAG"
    assert node.definition == "def" and node.golden is True


def test_build_graph_response_includes_concept_relation_edges(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-09-10T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-09-10T00:00:01Z")
    insert_edge(db_path, "e_1", "c_1", "c_2", "related", "summary")

    response = build_graph_response(tmp_path, db_path)

    assert len(response.edges) == 1
    edge = response.edges[0]
    assert edge.kind == "concept_relation" and edge.type == "related"


def test_build_graph_response_filters_dangling_edges(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-09-10T00:00:00Z")
    insert_edge(db_path, "e_dangling", "c_1", "c_missing", "related", "dangling")

    response = build_graph_response(tmp_path, db_path)

    assert response.edges == []
