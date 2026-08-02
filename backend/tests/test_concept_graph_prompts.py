import json

import pytest

from app.concept_graph.prompts import (
    build_dedup_prompt,
    build_extraction_prompt,
    parse_dedup_response,
    parse_extraction_response,
)


def test_build_extraction_prompt_includes_quote_and_note():
    prompt = build_extraction_prompt("no database, no cloud, no lock-in", "core design philosophy for Asterism")
    assert "no database, no cloud, no lock-in" in prompt
    assert "core design philosophy for Asterism" in prompt


def test_build_extraction_prompt_omits_note_section_when_none():
    prompt = build_extraction_prompt("some quote", None)
    assert "some quote" in prompt
    assert "User's note" not in prompt


def test_build_extraction_prompt_includes_few_shot_examples():
    prompt = build_extraction_prompt("some quote", None)
    assert "Example" in prompt or "example" in prompt


def test_build_extraction_prompt_includes_negative_example():
    prompt = build_extraction_prompt("some quote", None)
    assert "don't extract" in prompt.lower() or "too generic" in prompt.lower()


def test_build_extraction_prompt_allows_abstaining():
    prompt = build_extraction_prompt("some quote", None)
    assert "empty list" in prompt.lower() or "return []" in prompt.lower()


def test_build_extraction_prompt_requires_quote_anchoring():
    prompt = build_extraction_prompt("some quote", None)
    assert "quote" in prompt.lower()


def test_parse_extraction_response_accepts_empty_list():
    concepts = parse_extraction_response("[]")
    assert concepts == []


def test_parse_extraction_response_returns_concepts():
    raw = json.dumps([
        {"term": "Local-first storage", "definition": "Filesystem is the source of truth.", "self_relevant": False}
    ])
    concepts = parse_extraction_response(raw)
    assert concepts[0]["term"] == "Local-first storage"
    assert concepts[0]["self_relevant"] is False


def test_parse_extraction_response_raises_on_malformed_json():
    with pytest.raises(ValueError):
        parse_extraction_response("not json")


def test_parse_extraction_response_raises_on_object_instead_of_list():
    raw = json.dumps({"term": "Local-first storage", "definition": "def", "self_relevant": False})
    with pytest.raises(ValueError):
        parse_extraction_response(raw)


def test_parse_extraction_response_raises_on_missing_key():
    raw = json.dumps([{"term": "Local-first storage", "definition": "def"}])
    with pytest.raises(ValueError):
        parse_extraction_response(raw)


def test_parse_extraction_response_strips_json_markdown_fence():
    # Exact raw response reported by the user from a real gpt-4o call.
    raw = (
        '```json\n[\n    {\n        "term": "Future Vision",\n        '
        '"definition": "A statement indicating a perspective or prediction about what is to come.",\n        '
        '"self_relevant": false\n    }\n]\n```'
    )
    concepts = parse_extraction_response(raw)
    assert concepts[0]["term"] == "Future Vision"
    assert concepts[0]["self_relevant"] is False


def test_parse_extraction_response_strips_plain_markdown_fence():
    raw = "```\n" + json.dumps([
        {"term": "Local-first storage", "definition": "Filesystem is the source of truth.", "self_relevant": False}
    ]) + "\n```"
    concepts = parse_extraction_response(raw)
    assert concepts[0]["term"] == "Local-first storage"


def test_parse_extraction_response_raises_on_malformed_json_inside_fence():
    with pytest.raises(ValueError):
        parse_extraction_response("```json\nnot json\n```")


def test_build_dedup_prompt_includes_note_override_instruction():
    neighbors = [{"id": "c_1", "term": "Original vs. derived data model", "definition": "def"}]
    prompt = build_dedup_prompt(
        "Local-first storage", "def", "same idea as local-first but more specific", neighbors
    )
    assert "Original vs. derived data model" in prompt
    assert "override" in prompt.lower()


def test_build_dedup_prompt_asks_for_relationship_classification():
    # Relationship classification (contradicts/extends/related_to/none) moved
    # here from the extraction step (2026-07-31 amendment to the Phase 6b-2
    # design) so it works even when there's no note to draw from — Tier-1
    # digest concepts never have one.
    neighbors = [{"id": "c_1", "term": "X", "definition": "def"}]
    prompt = build_dedup_prompt("Y", "def", None, neighbors)
    assert "contradicts" in prompt.lower()
    assert "extends" in prompt.lower()
    assert "relationship" in prompt.lower()


def test_parse_dedup_response_returns_judgments():
    raw = json.dumps([
        {"existing_concept_id": "c_1", "judgment": "related_distinct", "confidence": "high",
         "relationship": "extends", "summary": "s"}
    ])
    judgments = parse_dedup_response(raw)
    assert judgments[0]["judgment"] == "related_distinct"
    assert judgments[0]["confidence"] == "high"
    assert judgments[0]["relationship"] == "extends"


def test_parse_dedup_response_strips_json_markdown_fence():
    raw = "```json\n" + json.dumps([
        {"existing_concept_id": "c_1", "judgment": "related_distinct", "confidence": "high",
         "relationship": "related_to", "summary": "s"}
    ]) + "\n```"
    judgments = parse_dedup_response(raw)
    assert judgments[0]["judgment"] == "related_distinct"


def test_parse_dedup_response_strips_plain_markdown_fence():
    raw = "```\n" + json.dumps([
        {"existing_concept_id": "c_1", "judgment": "same", "confidence": "high",
         "relationship": "none", "summary": "s"}
    ]) + "\n```"
    judgments = parse_dedup_response(raw)
    assert judgments[0]["judgment"] == "same"


def test_parse_dedup_response_raises_on_malformed_json_inside_fence():
    with pytest.raises(ValueError):
        parse_dedup_response("```json\nnot json\n```")


def test_parse_dedup_response_raises_on_object_instead_of_list():
    raw = json.dumps({"existing_concept_id": "c_1", "judgment": "same", "confidence": "high",
                       "relationship": "none", "summary": "s"})
    with pytest.raises(ValueError):
        parse_dedup_response(raw)


def test_parse_dedup_response_raises_on_missing_key():
    raw = json.dumps([{"existing_concept_id": "c_1", "judgment": "same", "confidence": "high",
                        "relationship": "none"}])
    with pytest.raises(ValueError):
        parse_dedup_response(raw)


def test_parse_dedup_response_raises_on_invalid_judgment():
    raw = json.dumps([
        {"existing_concept_id": "c_1", "judgment": "sort_of_the_same", "confidence": "high",
         "relationship": "extends", "summary": "s"}
    ])
    with pytest.raises(ValueError):
        parse_dedup_response(raw)


def test_parse_dedup_response_raises_on_invalid_confidence():
    raw = json.dumps([
        {"existing_concept_id": "c_1", "judgment": "same", "confidence": "very_high",
         "relationship": "extends", "summary": "s"}
    ])
    with pytest.raises(ValueError):
        parse_dedup_response(raw)


def test_parse_dedup_response_raises_on_invalid_relationship():
    raw = json.dumps([
        {"existing_concept_id": "c_1", "judgment": "same", "confidence": "high",
         "relationship": "is_basically_the_same_thing", "summary": "s"}
    ])
    with pytest.raises(ValueError):
        parse_dedup_response(raw)
