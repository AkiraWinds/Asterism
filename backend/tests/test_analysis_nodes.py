"""Tests for the analysis node functions."""

from unittest.mock import MagicMock

from app.analysis.nodes import run_claims, run_critique, run_digest, run_triage
from app.repositories.config_repository import AgentConfig


def _base_state():
    return {
        "title": "My Article",
        "content": "Some content about RAG reducing hallucination.",
        "data_root": "/tmp/fake",
        "config": AgentConfig(strategy="api-key", provider="anthropic", api_key="fake"),
    }


def _fake_provider(response_text: str):
    provider = MagicMock()
    provider.complete.return_value = response_text
    return provider


def test_run_triage_success(monkeypatch):
    provider = _fake_provider(
        '{"score": 78, "action": "worth_reading", "reason": "Specific and dense.", '
        '"read_time_minutes": 5, "density": 70, "originality": 60}'
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    result = run_triage(_base_state())

    assert result["triage"].score == 78
    assert result["triage"].action == "worth_reading"
    assert result["triage_error"] is None


def test_run_triage_skips_if_already_populated():
    provider = MagicMock()
    state = _base_state()
    state["triage"] = "already-set"

    result = run_triage(state)

    assert result == {}
    provider.complete.assert_not_called()


def test_run_triage_retries_once_then_returns_null_on_persistent_failure(monkeypatch):
    provider = _fake_provider("not json at all")
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    result = run_triage(_base_state())

    assert result["triage"] is None
    assert result["triage_error"] is not None
    assert provider.complete.call_count == 2


def test_run_digest_assigns_ids_and_carries_source_quote(monkeypatch):
    provider = _fake_provider(
        '{"summary": "A summary.", '
        '"highlights": [{"text": "RAG helps", "type": "insight", "source_quote": "RAG reducing hallucination"}], '
        '"concepts": [{"term": "RAG", "definition": "Retrieval-augmented generation."}], '
        '"structure": ["intro"]}'
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    result = run_digest(_base_state())

    assert result["digest"].summary == "A summary."
    assert result["digest"].highlights[0].id == "h1"
    assert result["digest"].highlights[0].source_quote == "RAG reducing hallucination"
    assert result["digest"].concepts[0].id == "c1"
    assert result["digest_error"] is None


def test_run_critique_success(monkeypatch):
    provider = _fake_provider(
        '{"hidden_assumptions": ["Assumes X."], "potential_issues": [], '
        '"needs_verification": [], "bias_indicators": []}'
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    result = run_critique(_base_state())

    assert result["critique"].hidden_assumptions == ["Assumes X."]
    assert result["critique_error"] is None


def test_run_claims_assigns_ids(monkeypatch):
    provider = _fake_provider(
        '{"claims": [{"text": "RAG reduces hallucination", "type": "factual", "source_quote": "RAG reducing hallucination"}]}'
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    result = run_claims(_base_state())

    assert result["claims"][0].id == "claim1"
    assert result["claims"][0].type == "factual"
    assert result["claims_error"] is None
