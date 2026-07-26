from app.analysis.prompts import (
    build_claims_prompt,
    build_coarse_filter_prompt,
    build_critique_prompt,
    build_detailed_compare_prompt,
    build_digest_prompt,
    build_triage_prompt,
)
from app.schemas.analysis import Claim


def test_triage_prompt_includes_title_content_and_score_bands():
    prompt = build_triage_prompt("My Article", "Some content here.")
    assert "My Article" in prompt
    assert "Some content here." in prompt
    assert "must_read" in prompt
    assert "do not penalize" in prompt.lower()


def test_digest_prompt_requires_source_quote_and_faithfulness():
    prompt = build_digest_prompt("My Article", "Some content here.")
    assert "source_quote" in prompt
    assert "do not infer" in prompt.lower() or "not infer" in prompt.lower()
    assert "paraphrase" in prompt.lower()


def test_critique_prompt_names_all_four_categories():
    prompt = build_critique_prompt("My Article", "Some content here.")
    for category in ["hidden_assumptions", "potential_issues", "needs_verification", "bias_indicators"]:
        assert category in prompt


def test_claims_prompt_caps_at_eight_and_requires_type():
    prompt = build_claims_prompt("My Article", "Some content here.")
    assert "8" in prompt
    assert "factual" in prompt and "opinion" in prompt and "prediction" in prompt


def test_coarse_filter_prompt_lists_existing_sources():
    prompt = build_coarse_filter_prompt(
        "New Article",
        "A summary of the new article.",
        [{"id": "abc123", "title": "Old Article", "summary": "A summary of the old one."}],
    )
    assert "New Article" in prompt
    assert "abc123" in prompt
    assert "Old Article" in prompt


def test_detailed_compare_prompt_lists_claims_on_both_sides():
    new_claims = [Claim(id="claim1", text="RAG reduces hallucination", type="factual", source_quote="x")]
    candidates = [
        {
            "id": "abc123",
            "title": "Old Article",
            "claims": [Claim(id="claim1", text="RAG does not eliminate hallucination", type="factual", source_quote="y")],
        }
    ]
    prompt = build_detailed_compare_prompt("new123", new_claims, candidates)
    assert "RAG reduces hallucination" in prompt
    assert "RAG does not eliminate hallucination" in prompt
    assert "abc123" in prompt
    assert "contradicts" in prompt
