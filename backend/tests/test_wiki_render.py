from app.wiki.render import (
    extract_body, parse_wiki_page_frontmatter, render_wiki_page,
    render_related_section, render_sources_section, render_index, render_log_entry,
    render_aspect_page,
)


def test_render_wiki_page_roundtrips_through_parse_frontmatter():
    text = render_wiki_page(
        concept_id="c_8f2a1b", term="RAG", updated_at="2026-07-31T10:00:00Z",
        source_highlight_count=5, source_provenance_hash="abc123",
        source_ids=["s_1", "s_2"], body="Synthesis paragraph.",
        related_section="", sources_section="",
    )

    frontmatter = parse_wiki_page_frontmatter(text)

    assert frontmatter == {
        "concept_id": "c_8f2a1b", "term": "RAG", "updated_at": "2026-07-31T10:00:00Z",
        "source_highlight_count": 5, "source_provenance_hash": "abc123",
        "source_ids": ["s_1", "s_2"],
    }


def test_render_wiki_page_includes_body_and_sections():
    text = render_wiki_page(
        concept_id="c_1", term="RAG", updated_at="2026-07-31T10:00:00Z",
        source_highlight_count=3, source_provenance_hash="abc",
        source_ids=["s_1"], body="Synthesis text.",
        related_section="## Related concepts\n\n- related thing\n",
        sources_section="## Sources\n\n- a quote\n",
    )

    assert "Synthesis text." in text
    assert "## Related concepts" in text
    assert "## Sources" in text


def test_parse_wiki_page_frontmatter_returns_none_without_frontmatter():
    assert parse_wiki_page_frontmatter("just plain text, no frontmatter") is None


def test_extract_body_returns_text_after_frontmatter():
    text = render_wiki_page(
        concept_id="c_1", term="RAG", updated_at="t", source_highlight_count=1,
        source_provenance_hash="h", source_ids=[], body="The actual synthesis.",
        related_section="", sources_section="",
    )
    assert "The actual synthesis." in extract_body(text)
    assert "concept_id" not in extract_body(text)


def test_render_related_section_empty_when_no_edges():
    assert render_related_section([], {}, {}, "c_1") == ""


def test_render_related_section_links_known_slug_and_plain_text_unknown():
    edges = [
        {"from_id": "c_1", "to_id": "c_2", "type": "extends", "summary": "builds on it"},
        {"from_id": "c_3", "to_id": "c_1", "type": "contradicts", "summary": "disputes it"},
    ]
    concept_terms = {"c_1": "RAG", "c_2": "Vector Search", "c_3": "Fine-tuning"}
    concept_slugs = {"c_2": "vector-search"}  # c_3 has no page yet

    section = render_related_section(edges, concept_terms, concept_slugs, "c_1")

    assert "[Vector Search](./vector-search.md)" in section
    assert "Fine-tuning" in section
    assert "[Fine-tuning]" not in section
    assert "**extends**" in section and "**contradicts**" in section


def test_render_sources_section_empty_when_no_citations():
    assert render_sources_section([]) == ""


def test_render_sources_section_shows_quote_when_present():
    section = render_sources_section([
        {"source_id": "s_1", "label": "Article A", "quote": "an exact quote"},
        {"source_id": "s_2", "label": "Article B", "quote": None},
    ])
    assert '- Article A — "an exact quote"' in section
    assert "- Article B" in section
    assert "Article B —" not in section


def test_render_index_lists_pages_and_omits_attention_when_empty():
    pages = [{
        "term": "RAG", "slug": "rag", "definition": "Retrieval-augmented generation.",
        "source_highlight_count": 5, "updated_at": "2026-07-31T10:00:00Z",
    }]
    index = render_index(pages, [])
    assert "[RAG](rag.md)" in index
    assert "5 highlights" in index
    assert "updated 2026-07-31" in index
    assert "Needs attention" not in index


def test_render_index_includes_attention_section_when_present():
    index = render_index([], ["Orphan: [X](x.md) — no edges to any other concept"])
    assert "## Needs attention" in index
    assert "Orphan: [X](x.md)" in index


def test_render_index_truncates_long_definition_and_strips_newlines():
    pages = [{
        "term": "RAG", "slug": "rag",
        "definition": "line one\nline two\n" + ("word " * 60),
        "source_highlight_count": 1, "updated_at": "2026-07-31T10:00:00Z",
    }]

    index = render_index(pages, [])

    # Definition became one list-item line (no raw newline broke the markdown).
    line = next(line for line in index.splitlines() if line.startswith("- [RAG]"))
    assert line.startswith("- [RAG](rag.md) — line one line two word word")
    definition_part = line.split("— ", 1)[1].split(" · ")[0]
    assert len(definition_part) <= 151
    assert definition_part.endswith("…")


def test_render_log_entry_formats_summary_line_and_changes():
    entry = render_log_entry(
        date="2026-07-31", pages_updated=4, pages_new=1, orphans_flagged=0, errors_count=0,
        change_lines=["- updated: RAG (3→5 highlights)", "- new: Prompt Caching"],
    )
    assert entry.startswith("## [2026-07-31] wiki-compile | 4 pages updated, 1 new, 0 orphans flagged, 0 errors\n")
    assert "- updated: RAG (3→5 highlights)" in entry
    assert entry.endswith("\n\n")


def test_render_log_entry_handles_no_changes():
    entry = render_log_entry("2026-07-31", 0, 0, 0, 0, [])
    assert "0 pages updated, 0 new, 0 orphans flagged, 0 errors" in entry


def test_render_log_entry_ends_with_blank_line_so_appended_entries_stay_separated():
    first = render_log_entry("2026-07-31", 1, 0, 0, 0, ["- updated: RAG"])
    second = render_log_entry("2026-08-01", 0, 1, 0, 0, ["- new: Vector Search"])

    appended = first + second

    assert "\n\n## [2026-08-01]" in appended


def test_render_wiki_page_includes_aspects_frontmatter_when_provided():
    text = render_wiki_page(
        concept_id="c_1", term="RAG", updated_at="2026-08-01T00:00:00Z",
        source_highlight_count=12, source_provenance_hash="abc",
        source_ids=["s_1"], body="Overview prose.",
        related_section="", sources_section="",
        aspects=["rag-retrieval-strategies", "rag-evaluation"],
    )
    frontmatter = parse_wiki_page_frontmatter(text)
    assert frontmatter["aspects"] == ["rag-retrieval-strategies", "rag-evaluation"]


def test_render_wiki_page_omits_aspects_frontmatter_when_not_split():
    text = render_wiki_page(
        concept_id="c_1", term="RAG", updated_at="2026-08-01T00:00:00Z",
        source_highlight_count=3, source_provenance_hash="abc",
        source_ids=["s_1"], body="Single page.", related_section="", sources_section="",
    )
    assert "aspects" not in parse_wiki_page_frontmatter(text)


def test_render_aspect_page_roundtrips_through_parse_frontmatter():
    text = render_aspect_page(
        concept_id="c_1", term="Evaluation", aspect_of="rag",
        updated_at="2026-08-01T00:00:00Z", source_ids=["s_1", "s_2"], body="Evaluation prose.",
    )
    frontmatter = parse_wiki_page_frontmatter(text)
    assert frontmatter == {
        "concept_id": "c_1", "term": "Evaluation", "aspect_of": "rag",
        "updated_at": "2026-08-01T00:00:00Z", "source_ids": ["s_1", "s_2"],
    }
    assert "Evaluation prose." in extract_body(text)


def test_render_index_nests_aspect_pages_under_their_overview():
    pages = [{
        "term": "RAG", "slug": "rag", "definition": "def.",
        "source_highlight_count": 12, "updated_at": "2026-08-01T00:00:00Z",
        "aspect_pages": [
            {"term": "Retrieval Strategies", "slug": "rag-retrieval-strategies"},
            {"term": "Evaluation", "slug": "rag-evaluation"},
        ],
    }]
    index = render_index(pages, [])
    lines = index.splitlines()
    rag_line_idx = next(i for i, l in enumerate(lines) if l.startswith("- [RAG]"))
    assert lines[rag_line_idx + 1] == "  - [Retrieval Strategies](rag-retrieval-strategies.md)"
    assert lines[rag_line_idx + 2] == "  - [Evaluation](rag-evaluation.md)"


def test_render_index_unsplit_concept_has_no_nested_lines():
    pages = [{
        "term": "Vector Search", "slug": "vector-search", "definition": "def.",
        "source_highlight_count": 4, "updated_at": "2026-08-01T00:00:00Z",
        "aspect_pages": [],
    }]
    index = render_index(pages, [])
    assert "  - [" not in index
