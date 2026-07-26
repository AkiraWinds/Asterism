import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisResult,
    Claim,
    Concept,
    Connection,
    Critique,
    Digest,
    Highlight,
    Triage,
)


def test_triage_accepts_valid_action():
    triage = Triage(
        score=78,
        action="worth_reading",
        reason="Concrete and specific.",
        read_time_minutes=6,
        density=70,
        originality=55,
    )
    assert triage.action == "worth_reading"


def test_triage_rejects_invalid_action():
    with pytest.raises(ValidationError):
        Triage(
            score=78,
            action="not_a_real_action",
            reason="x",
            read_time_minutes=6,
            density=70,
            originality=55,
        )


def test_highlight_requires_source_quote():
    highlight = Highlight(id="h1", text="AI reads first", type="insight", source_quote="the AI reads first")
    assert highlight.source_quote == "the AI reads first"
    with pytest.raises(ValidationError):
        Highlight(id="h1", text="AI reads first", type="insight")


def test_digest_defaults_lists_to_empty():
    digest = Digest(summary="A summary.")
    assert digest.highlights == []
    assert digest.concepts == []
    assert digest.structure == []


def test_critique_defaults_lists_to_empty():
    critique = Critique()
    assert critique.hidden_assumptions == []
    assert critique.potential_issues == []
    assert critique.needs_verification == []
    assert critique.bias_indicators == []


def test_claim_rejects_invalid_type():
    with pytest.raises(ValidationError):
        Claim(id="claim1", text="RAG reduces hallucination", type="not_a_type", source_quote="x")


def test_connection_rejects_invalid_type():
    with pytest.raises(ValidationError):
        Connection(id="conn1", type="not_a_type", summary="s", details="d")


def test_analysis_result_allows_null_fields_with_error():
    result = AnalysisResult(
        triage=None,
        triage_error="provider timeout",
        digest=None,
        digest_error=None,
        critique=None,
        critique_error=None,
        claims=None,
        claims_error=None,
        connections=[],
        analyzed_at="2026-07-26T12:00:00+00:00",
    )
    assert result.triage is None
    assert result.triage_error == "provider timeout"
    assert result.connections == []


def test_concept_model():
    concept = Concept(id="c1", term="RAG", definition="Retrieval-augmented generation.")
    assert concept.term == "RAG"
