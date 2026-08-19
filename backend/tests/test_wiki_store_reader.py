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


# scan_wiki_pages tests
from app.wiki.store_reader import scan_wiki_pages


def test_scan_wiki_pages_finds_pages_by_concept_id(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "rag.md").write_text(
        '---\nconcept_id: "c_1"\nterm: "RAG"\nupdated_at: "2026-08-01T00:00:00Z"\n'
        'source_highlight_count: 3\nsource_provenance_hash: "abc"\nsource_ids: []\n---\n\nBody text.\n'
    )

    pages = scan_wiki_pages(wiki_dir)

    assert pages == {"c_1": {"slug": "rag", "frontmatter": {
        "concept_id": "c_1", "term": "RAG", "updated_at": "2026-08-01T00:00:00Z",
        "source_highlight_count": 3, "source_provenance_hash": "abc", "source_ids": [],
    }}}


def test_scan_wiki_pages_skips_index_and_log(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "index.md").write_text("# Wiki Index\n")
    (wiki_dir / "log.md").write_text("## [2026-08-01] wiki-compile\n")

    assert scan_wiki_pages(wiki_dir) == {}


def test_scan_wiki_pages_skips_unparseable_frontmatter(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "broken.md") .write_text("---\nterm: not valid json\n---\n\nBody.\n")

    assert scan_wiki_pages(wiki_dir) == {}


def test_scan_wiki_pages_skips_aspect_pages(tmp_path: Path):
    # Forward-compat with PR #13 (feat/wiki-concept-split): an aspect page
    # carries the *same* concept_id as its parent overview page plus an
    # `aspect_of` key. Without this exclusion, a concept with aspect pages
    # would resolve ambiguously (multiple files matching one concept_id).
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "rag.md").write_text(
        '---\nconcept_id: "c_1"\nterm: "RAG"\nupdated_at: "2026-08-01T00:00:00Z"\n'
        'source_highlight_count: 3\nsource_provenance_hash: "abc"\nsource_ids: []\n---\n\nOverview.\n'
    )
    (wiki_dir / "rag-evaluation.md").write_text(
        '---\nconcept_id: "c_1"\nterm: "Evaluation"\naspect_of: "rag"\n'
        'updated_at: "2026-08-01T00:00:00Z"\nsource_ids: []\n---\n\nAspect body.\n'
    )

    pages = scan_wiki_pages(wiki_dir)

    assert list(pages.keys()) == ["c_1"]
    assert pages["c_1"]["slug"] == "rag"


# get_wiki_page_by_concept_id and get_wiki_page_by_slug tests
from app.wiki.store_reader import get_wiki_page_by_concept_id, get_wiki_page_by_slug


def _write_overview_page(wiki_dir: Path, slug: str, concept_id: str, term: str, aspects: list[str] | None = None) -> None:
    aspects_line = f'\naspects: {json.dumps(aspects)}' if aspects else ""
    (wiki_dir / f"{slug}.md").write_text(
        f'---\nconcept_id: {json.dumps(concept_id)}\nterm: {json.dumps(term)}\n'
        f'updated_at: "2026-08-01T00:00:00Z"\nsource_highlight_count: 3\n'
        f'source_provenance_hash: "abc"\nsource_ids: []{aspects_line}\n---\n\nOverview body.\n\n'
        f'## Related concepts\n\nSome related text.\n'
    )


def _write_aspect_page(wiki_dir: Path, slug: str, concept_id: str, term: str, aspect_of: str) -> None:
    (wiki_dir / f"{slug}.md").write_text(
        f'---\nconcept_id: {json.dumps(concept_id)}\nterm: {json.dumps(term)}\n'
        f'aspect_of: {json.dumps(aspect_of)}\nupdated_at: "2026-08-01T00:00:00Z"\n'
        f'source_ids: []\n---\n\nAspect body.\n'
    )


def test_get_wiki_page_by_concept_id_returns_body_and_no_aspects(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    _write_overview_page(wiki_dir, "rag", "c_1", "RAG")

    page = get_wiki_page_by_concept_id(wiki_dir, "c_1")

    assert page["slug"] == "rag"
    assert page["term"] == "RAG"
    assert page["updated_at"] == "2026-08-01T00:00:00Z"
    assert "Overview body." in page["body"]
    assert "## Related concepts" in page["body"]  # full body, not synthesis-only
    assert page["aspects"] == []


def test_get_wiki_page_by_concept_id_returns_none_when_not_found(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    assert get_wiki_page_by_concept_id(wiki_dir, "c_missing") is None


def test_get_wiki_page_by_concept_id_resolves_aspect_terms(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    _write_overview_page(wiki_dir, "rag", "c_1", "RAG", aspects=["rag-evaluation"])
    _write_aspect_page(wiki_dir, "rag-evaluation", "c_1", "Evaluation", "rag")

    page = get_wiki_page_by_concept_id(wiki_dir, "c_1")

    assert page["aspects"] == [{"slug": "rag-evaluation", "term": "Evaluation"}]


def test_get_wiki_page_by_concept_id_skips_aspect_slug_with_missing_file(tmp_path: Path):
    # The overview's recorded aspects list can point at a file that's since
    # been deleted (e.g. a hand-edit) — don't crash, just omit it.
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    _write_overview_page(wiki_dir, "rag", "c_1", "RAG", aspects=["rag-missing"])

    page = get_wiki_page_by_concept_id(wiki_dir, "c_1")

    assert page["aspects"] == []


def test_get_wiki_page_by_slug_returns_body(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    _write_aspect_page(wiki_dir, "rag-evaluation", "c_1", "Evaluation", "rag")

    page = get_wiki_page_by_slug(wiki_dir, "rag-evaluation")

    assert page == {
        "slug": "rag-evaluation", "term": "Evaluation",
        "updated_at": "2026-08-01T00:00:00Z", "body": "Aspect body.\n",
        "aspects": [],
    }


def test_get_wiki_page_by_slug_returns_none_when_file_missing(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    assert get_wiki_page_by_slug(wiki_dir, "nonexistent") is None
