import pytest

from app.wiki.prompts import build_wiki_page_prompt, parse_wiki_page_response


def test_build_wiki_page_prompt_includes_term_definition_and_citations():
    prompt = build_wiki_page_prompt(
        term="RAG", definition="Retrieval-augmented generation.",
        citations=[{"source_id": "s_1", "label": "Article A", "quote": "an exact quote"}],
        edges=[],
    )
    assert "RAG" in prompt
    assert "Retrieval-augmented generation." in prompt
    assert "an exact quote" in prompt


def test_build_wiki_page_prompt_mentions_edges_when_present():
    prompt = build_wiki_page_prompt(
        term="RAG", definition="def", citations=[],
        edges=[{"from_id": "c_1", "to_id": "c_2", "type": "contradicts", "summary": "disputes fine-tuning"}],
    )
    assert "contradicts" in prompt
    assert "disputes fine-tuning" in prompt


def test_build_wiki_page_prompt_mentions_aspect_splitting_option():
    prompt = build_wiki_page_prompt(term="RAG", definition="def", citations=[], edges=[])
    assert "aspects" in prompt.lower()


def test_parse_wiki_page_response_extracts_synthesis_with_no_aspects():
    raw = '{"synthesis": "RAG grounds generation in retrieved passages."}'
    assert parse_wiki_page_response(raw) == {
        "overview": "RAG grounds generation in retrieved passages.",
        "aspects": [],
        "warnings": [],
    }


def test_parse_wiki_page_response_extracts_aspects_when_present():
    raw = (
        '{"synthesis": "RAG overview.", "aspects": ['
        '{"title": "Retrieval Strategies", "content": "Strategy prose."}, '
        '{"title": "Evaluation", "content": "Evaluation prose."}'
        "]}"
    )
    assert parse_wiki_page_response(raw) == {
        "overview": "RAG overview.",
        "aspects": [
            {"title": "Retrieval Strategies", "content": "Strategy prose."},
            {"title": "Evaluation", "content": "Evaluation prose."},
        ],
        "warnings": [],
    }


def test_parse_wiki_page_response_treats_null_aspects_as_empty():
    raw = '{"synthesis": "text", "aspects": null}'
    assert parse_wiki_page_response(raw) == {"overview": "text", "aspects": [], "warnings": []}


def test_parse_wiki_page_response_drops_malformed_aspect_entry_with_warning():
    raw = (
        '{"synthesis": "text", "aspects": ['
        '{"title": "Good", "content": "fine"}, '
        '{"title": "Missing content"}'
        "]}"
    )
    result = parse_wiki_page_response(raw)
    assert result["overview"] == "text"
    assert result["aspects"] == [{"title": "Good", "content": "fine"}]
    assert len(result["warnings"]) == 1


def test_parse_wiki_page_response_treats_non_list_aspects_as_empty_with_warning():
    raw = '{"synthesis": "text", "aspects": "not a list"}'
    result = parse_wiki_page_response(raw)
    assert result == {"overview": "text", "aspects": [], "warnings": [result["warnings"][0]]}


def test_parse_wiki_page_response_strips_markdown_fence():
    raw = '```json\n{"synthesis": "text"}\n```'
    assert parse_wiki_page_response(raw)["overview"] == "text"


def test_parse_wiki_page_response_raises_on_malformed_json():
    with pytest.raises(ValueError):
        parse_wiki_page_response("not json")


def test_parse_wiki_page_response_raises_when_synthesis_missing():
    with pytest.raises(ValueError):
        parse_wiki_page_response('{"other_key": "text"}')
