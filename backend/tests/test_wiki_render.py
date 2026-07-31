from app.wiki.render import extract_body, parse_wiki_page_frontmatter, render_wiki_page


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
