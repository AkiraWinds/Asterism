from unittest.mock import MagicMock

from app.analysis.graph import build_analysis_graph
from app.repositories.config_repository import AgentConfig
from app.schemas.analysis import Critique, Digest


def _fake_provider(responses: dict[str, str]):
    """responses maps a substring of the prompt to the canned response for that call."""
    provider = MagicMock()

    def _complete(prompt: str) -> str:
        for marker, response in responses.items():
            if marker in prompt:
                return response
        raise AssertionError(f"No canned response configured for prompt: {prompt[:200]}")

    provider.complete.side_effect = _complete
    return provider


def test_graph_fans_out_and_produces_full_result(tmp_path, monkeypatch):
    provider = _fake_provider(
        {
            "Score how much attention": '{"score": 78, "action": "worth_reading", "reason": "x", "read_time_minutes": 5, "density": 70, "originality": 60}',
            "Summarize this content": '{"summary": "A summary.", "highlights": [], "concepts": [], "structure": []}',
            "Critically evaluate": '{"hidden_assumptions": [], "potential_issues": [], "needs_verification": [], "bias_indicators": []}',
            "Extract up to 8": '{"claims": []}',
        }
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    graph = build_analysis_graph()
    state = {
        "source_id": "source1",
        "title": "My Article",
        "content": "Some content.",
        "data_root": tmp_path,
        "config": AgentConfig(strategy="api-key", provider="anthropic", api_key="fake"),
    }

    output = graph.invoke(state)

    result = output["result"]
    assert result.triage.score == 78
    assert result.digest.summary == "A summary."
    assert result.critique.hidden_assumptions == []
    assert result.claims == []
    assert result.connections == []


def test_graph_resume_only_recomputes_failed_field(tmp_path, monkeypatch):
    call_log = []

    def _complete(prompt: str) -> str:
        if "Score how much attention" in prompt:
            call_log.append("triage")
            return '{"score": 90, "action": "must_read", "reason": "x", "read_time_minutes": 5, "density": 90, "originality": 90}'
        raise AssertionError(f"Unexpected call for prompt: {prompt[:200]}")

    provider = MagicMock()
    provider.complete.side_effect = _complete
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    graph = build_analysis_graph()
    state = {
        "source_id": "source1",
        "title": "My Article",
        "content": "Some content.",
        "data_root": tmp_path,
        "config": AgentConfig(strategy="api-key", provider="anthropic", api_key="fake"),
        "triage": None,
        "triage_error": "previous timeout",
        # Non-None sentinels (of the correct type, so finalize's strict
        # AnalysisResult validation still succeeds) so run_digest/
        # run_critique/run_claims see them as already populated and skip.
        "digest": Digest(summary="already-set-sentinel"),
        "critique": Critique(),
        "claims": [],
    }

    graph.invoke(state)

    assert call_log == ["triage"]
