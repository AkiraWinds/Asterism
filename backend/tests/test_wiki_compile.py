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
