# backend/tests/test_wiki_compile.py
from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, insert_concept, insert_edge, link_concept_highlight
from app.providers.base import Provider, ProviderError
from app.wiki.compile import run_compile


class StubProvider(Provider):
    def __init__(self, response: str | None = None, raise_error: bool = False):
        self.response = response or '{"synthesis": "Stub synthesis text."}'
        self.raise_error = raise_error
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if self.raise_error:
            raise ProviderError("stub failure")
        return self.response


def _seed_qualifying_concept(tmp_path: Path, concept_id: str = "c_1", term: str = "RAG") -> Path:
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, concept_id, term, "Retrieval-augmented generation.", [0.1], False, "2026-07-31T00:00:00Z")
    for i in range(3):
        link_concept_highlight(db_path, concept_id, f"s_{i}", f"h_{i}")
    return db_path


def test_run_compile_creates_page_for_qualifying_concept(tmp_path: Path):
    _seed_qualifying_concept(tmp_path)
    provider = StubProvider()

    result = run_compile(tmp_path, provider)

    assert result == {"pages_updated": 0, "pages_new": 1, "orphans_flagged": 1, "errors": []}
    page_text = (tmp_path / "wiki" / "rag.md").read_text()
    assert "Stub synthesis text." in page_text
    assert (tmp_path / "wiki" / "index.md").exists()
    assert (tmp_path / "wiki" / "log.md").exists()
    assert "1 new" in (tmp_path / "wiki" / "log.md").read_text()


def test_run_compile_skips_concept_below_threshold(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "RAG", "def", [0.1], False, "2026-07-31T00:00:00Z")
    link_concept_highlight(db_path, "c_1", "s_0", "h_0")  # only 1 provenance row

    result = run_compile(tmp_path, StubProvider())

    assert result["pages_new"] == 0
    assert not (tmp_path / "wiki" / "rag.md").exists()


def test_run_compile_second_run_with_no_changes_is_a_noop(tmp_path: Path):
    _seed_qualifying_concept(tmp_path)
    provider = StubProvider()
    run_compile(tmp_path, provider)
    calls_after_first_run = provider.calls

    result = run_compile(tmp_path, provider)

    assert result == {"pages_updated": 0, "pages_new": 0, "orphans_flagged": 1, "errors": []}
    assert provider.calls == calls_after_first_run  # no LLM call for the unchanged concept
    assert "0 pages updated, 0 new" in (tmp_path / "wiki" / "log.md").read_text().splitlines()[-1]


def test_run_compile_keeps_stable_slug_across_runs(tmp_path: Path):
    _seed_qualifying_concept(tmp_path)
    run_compile(tmp_path, StubProvider())
    link_concept_highlight(graph_db_path(tmp_path), "c_1", "s_3", "h_3")  # provenance changes -> regenerate

    run_compile(tmp_path, StubProvider())

    assert (tmp_path / "wiki" / "rag.md").exists()
    assert not (tmp_path / "wiki" / "rag-c1.md").exists()


def test_run_compile_treats_corrupt_existing_page_as_new_without_aborting(tmp_path: Path):
    # Wiki pages are user-editable output. A hand-edit that leaves invalid
    # JSON on a frontmatter line (unquoted `term:` value here) must not
    # crash the whole compile run -- the concept should just regenerate.
    _seed_qualifying_concept(tmp_path)
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "rag.md").write_text(
        "---\n"
        "concept_id: \"c_1\"\n"
        "term: RAG unquoted and broken\n"  # invalid JSON value -> json.JSONDecodeError
        "updated_at: \"2026-07-30T00:00:00+00:00\"\n"
        "source_highlight_count: 3\n"
        'source_provenance_hash: "deadbeef"\n'
        'source_ids: ["s_0"]\n'
        "---\n\n"
        "Old body.\n"
    )

    result = run_compile(tmp_path, StubProvider())

    assert result["errors"] == []
    assert result["pages_new"] == 1
    page_text = (tmp_path / "wiki" / "rag.md").read_text()
    assert "Stub synthesis text." in page_text


def test_run_compile_treats_missing_updated_at_as_not_unchanged(tmp_path: Path):
    # A page with otherwise-valid, parseable frontmatter but a deleted
    # `updated_at` line must fall through to regeneration instead of
    # raising KeyError from the `unchanged` branch.
    _seed_qualifying_concept(tmp_path)
    provider = StubProvider()
    run_compile(tmp_path, provider)  # first run creates rag.md with a real hash

    page_path = tmp_path / "wiki" / "rag.md"
    text = page_path.read_text()
    lines = [line for line in text.splitlines() if not line.startswith("updated_at:")]
    page_path.write_text("\n".join(lines) + "\n")

    result = run_compile(tmp_path, provider)

    assert result["errors"] == []
    # source_provenance_hash still matches, but missing updated_at means
    # "not unchanged" -> regenerated, so it counts as an update not a no-op.
    assert result["pages_updated"] == 1
    assert result["pages_new"] == 0


def test_run_compile_records_per_concept_llm_error_without_aborting(tmp_path: Path):
    db_path = _seed_qualifying_concept(tmp_path, "c_1", "RAG")
    insert_concept(db_path, "c_2", "Vector Search", "def2", [0.2], False, "2026-07-31T00:00:00Z")
    for i in range(3):
        link_concept_highlight(db_path, "c_2", f"t_{i}", f"g_{i}")
    insert_edge(db_path, "e_1", "c_1", "c_2", "related", "RAG uses vector search")

    result = run_compile(tmp_path, StubProvider(raise_error=True))

    assert result["pages_new"] == 0
    assert len(result["errors"]) == 2
    assert {e["concept_id"] for e in result["errors"]} == {"c_1", "c_2"}
