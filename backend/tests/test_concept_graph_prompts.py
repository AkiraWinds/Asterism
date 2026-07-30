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


def test_parse_extraction_response_returns_concepts():
    raw = json.dumps([
        {"term": "Local-first storage", "definition": "Filesystem is the source of truth.",
         "self_relevant": False, "relationship": "none"}
    ])
    concepts = parse_extraction_response(raw)
    assert concepts[0]["term"] == "Local-first storage"
    assert concepts[0]["relationship"] == "none"


def test_parse_extraction_response_raises_on_malformed_json():
    with pytest.raises(ValueError):
        parse_extraction_response("not json")


def test_build_dedup_prompt_includes_note_override_instruction():
    neighbors = [{"id": "c_1", "term": "Original vs. derived data model", "definition": "def"}]
    prompt = build_dedup_prompt(
        "Local-first storage", "def", "same idea as local-first but more specific", neighbors
    )
    assert "Original vs. derived data model" in prompt
    assert "override" in prompt.lower()


def test_parse_dedup_response_returns_judgments():
    raw = json.dumps([
        {"existing_concept_id": "c_1", "judgment": "related_distinct", "confidence": "high", "summary": "s"}
    ])
    judgments = parse_dedup_response(raw)
    assert judgments[0]["judgment"] == "related_distinct"
    assert judgments[0]["confidence"] == "high"
