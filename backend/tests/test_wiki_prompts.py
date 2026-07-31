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


def test_parse_wiki_page_response_extracts_synthesis():
    raw = '{"synthesis": "RAG grounds generation in retrieved passages."}'
    assert parse_wiki_page_response(raw) == "RAG grounds generation in retrieved passages."


def test_parse_wiki_page_response_strips_markdown_fence():
    raw = '```json\n{"synthesis": "text"}\n```'
    assert parse_wiki_page_response(raw) == "text"


def test_parse_wiki_page_response_raises_on_malformed_json():
    with pytest.raises(ValueError):
        parse_wiki_page_response("not json")


def test_parse_wiki_page_response_raises_when_synthesis_missing():
    with pytest.raises(ValueError):
        parse_wiki_page_response('{"other_key": "text"}')
