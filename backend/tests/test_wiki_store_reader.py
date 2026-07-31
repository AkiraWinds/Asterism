import sqlite3
from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, insert_edge, link_concept_highlight, link_concept_source
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
    link_concept_source(db_path, "c_1", "s_c")

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


# resolve_citations tests
import json

from app.wiki.store_reader import resolve_citations


def _write_source(tmp_path: Path, source_id: str, title: str) -> None:
    source_dir = tmp_path / "library" / source_id
    source_dir.mkdir(parents=True)
    (source_dir / "meta.json").write_text(json.dumps({
        "id": source_id, "original_title": title, "created_at": "2026-07-31T00:00:00Z",
    }))
    (source_dir / "content.md").write_text(f"---\ntitle: {json.dumps(title)}\n---\n\nbody\n")


def _write_highlight(tmp_path: Path, source_id: str, highlight_id: str, quote: str, source_title: str) -> None:
    source_dir = tmp_path / "library" / source_id
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "highlights.json").write_text(json.dumps({
        "highlights": [{
            "id": highlight_id, "source_quote": quote, "note": None,
            "source_title": source_title, "source_url": None, "created_at": "2026-07-31T00:00:00Z",
        }]
    }))


def test_resolve_citations_uses_highlight_quote_and_title(tmp_path: Path):
    _write_highlight(tmp_path, "s_a", "h_1", "the exact quote", "Article A")

    citations = resolve_citations(tmp_path, [{"source_id": "s_a", "highlight_id": "h_1"}])

    assert citations == [{"source_id": "s_a", "label": "Article A", "quote": "the exact quote"}]


def test_resolve_citations_falls_back_to_source_title_when_no_highlight_id(tmp_path: Path):
    _write_source(tmp_path, "s_b", "Article B")

    citations = resolve_citations(tmp_path, [{"source_id": "s_b", "highlight_id": None}])

    assert citations == [{"source_id": "s_b", "label": "Article B", "quote": None}]


def test_resolve_citations_falls_back_to_source_id_when_nothing_resolves(tmp_path: Path):
    citations = resolve_citations(tmp_path, [{"source_id": "s_missing", "highlight_id": None}])

    assert citations == [{"source_id": "s_missing", "label": "s_missing", "quote": None}]
