from app.wiki.render import (
    extract_body, parse_wiki_page_frontmatter, render_wiki_page,
    render_related_section, render_sources_section, render_index, render_log_entry,
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


def test_render_log_entry_formats_summary_line_and_changes():
    entry = render_log_entry(
        date="2026-07-31", pages_updated=4, pages_new=1, orphans_flagged=0, errors_count=0,
        change_lines=["- updated: RAG (3→5 highlights)", "- new: Prompt Caching"],
    )
    assert entry.startswith("## [2026-07-31] wiki-compile | 4 pages updated, 1 new, 0 orphans flagged, 0 errors\n")
    assert "- updated: RAG (3→5 highlights)" in entry
    assert entry.endswith("\n")


def test_render_log_entry_handles_no_changes():
    entry = render_log_entry("2026-07-31", 0, 0, 0, 0, [])
    assert "0 pages updated, 0 new, 0 orphans flagged, 0 errors" in entry
