import json
from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, insert_concept, insert_edge, link_concept_source
from app.graph_store.view import build_graph_response


def _new_db(tmp_path: Path) -> Path:
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    return db_path


def _write_source(tmp_path: Path, source_id: str, title: str) -> None:
    source_dir = tmp_path / "library" / source_id
    source_dir.mkdir(parents=True)
    (source_dir / "meta.json").write_text(json.dumps({
        "id": source_id, "original_title": title, "created_at": "2026-09-10T00:00:00Z", "type": "html",
    }))
    (source_dir / "content.md").write_text(f"---\ntitle: {json.dumps(title)}\n---\n\nbody\n")


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


def test_build_graph_response_includes_source_node_from_provenance(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-09-10T00:00:00Z")
    link_concept_source(db_path, "c_1", "s_1")
    _write_source(tmp_path, "s_1", "An Article")

    response = build_graph_response(tmp_path, db_path)

    source_nodes = [n for n in response.nodes if n.kind == "source"]
    assert len(source_nodes) == 1
    assert source_nodes[0].id == "src_s_1" and source_nodes[0].term == "An Article"
    link_edges = [e for e in response.edges if e.kind == "source_link"]
    assert len(link_edges) == 1
    assert link_edges[0].from_id == "c_1" and link_edges[0].to_id == "src_s_1"


def test_build_graph_response_dedupes_source_shared_by_two_concepts(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "A", "def", [0.1], False, "2026-09-10T00:00:00Z")
    insert_concept(db_path, "c_2", "B", "def", [0.2], False, "2026-09-10T00:00:01Z")
    link_concept_source(db_path, "c_1", "s_1")
    link_concept_source(db_path, "c_2", "s_1")
    _write_source(tmp_path, "s_1", "Shared Article")

    response = build_graph_response(tmp_path, db_path)

    assert len([n for n in response.nodes if n.kind == "source"]) == 1
    assert len([e for e in response.edges if e.kind == "source_link"]) == 2


def test_build_graph_response_skips_provenance_for_deleted_source(tmp_path: Path):
    db_path = _new_db(tmp_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-09-10T00:00:00Z")
    link_concept_source(db_path, "c_1", "s_missing")
    # no _write_source call — s_missing was deleted (or never existed)

    response = build_graph_response(tmp_path, db_path)

    assert [n for n in response.nodes if n.kind == "source"] == []
    assert [e for e in response.edges if e.kind == "source_link"] == []
