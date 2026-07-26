"""Tests for the top-level system graph: verifies it runs the analysis
subgraph via the "analyze" node and that partial results carry forward on
retry (only unresolved fields get recomputed).

Uses a prompt-marker-keyed fake provider (matching the pattern in
tests/test_analysis_graph.py) rather than a fixed MagicMock.side_effect
list: the analysis subgraph fans out to 4 parallel nodes (triage, digest,
critique, claims) whose LangGraph execution order is not guaranteed, so a
plain ordered side_effect list is flaky — it can hand the triage node the
digest node's canned response depending on scheduling order.
"""

from unittest.mock import MagicMock

from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_system_graph
from app.repositories.config_repository import AgentConfig
from app.schemas.analysis import AnalysisResult, Critique, Digest


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


def test_system_graph_runs_analyze_node_and_returns_result(monkeypatch):
    provider = _fake_provider(
        {
            "Score how much attention": '{"score": 78, "action": "worth_reading", "reason": "x", "read_time_minutes": 5, "density": 70, "originality": 60}',
            "Summarize this content": '{"summary": "A summary.", "highlights": [], "concepts": [], "structure": []}',
            "Critically evaluate": '{"hidden_assumptions": [], "potential_issues": [], "needs_verification": [], "bias_indicators": []}',
            "Extract up to 8": '{"claims": []}',
        }
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    graph = build_system_graph(MemorySaver())
    state = {
        "source_id": "source1",
        "title": "My Article",
        "content": "Some content.",
        "data_root": "/tmp/fake",
        "config": AgentConfig(strategy="api-key", provider="anthropic", api_key="fake"),
        "result": None,
    }

    output = graph.invoke(state, config={"configurable": {"thread_id": "source1"}})

    assert output["result"].triage.score == 78
    assert output["result"].digest.summary == "A summary."


def test_system_graph_carries_forward_existing_partial_result(monkeypatch):
    call_log = []

    def _complete(prompt: str) -> str:
        if "Score how much attention" in prompt:
            call_log.append("triage")
            return '{"score": 90, "action": "must_read", "reason": "x", "read_time_minutes": 5, "density": 90, "originality": 90}'
        raise AssertionError(f"Unexpected call for prompt: {prompt[:200]}")

    provider = MagicMock()
    provider.complete.side_effect = _complete
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    graph = build_system_graph(MemorySaver())
    # Non-None sentinels for digest/critique/claims (of the correct type, so
    # finalize's strict AnalysisResult validation still succeeds) so the
    # corresponding analysis nodes see them as already populated and skip
    # recomputation, mirroring the "already-set-sentinel" pattern in
    # tests/test_analysis_graph.py::test_graph_resume_only_recomputes_failed_field.
    existing = AnalysisResult(
        triage=None,
        triage_error="previous timeout",
        digest=Digest(summary="Already succeeded."),
        connections=[],
        claims=[],
        critique=Critique(),
        analyzed_at="2026-07-26T12:00:00+00:00",
    )
    state = {
        "source_id": "source1",
        "title": "My Article",
        "content": "Some content.",
        "data_root": "/tmp/fake",
        "config": AgentConfig(strategy="api-key", provider="anthropic", api_key="fake"),
        "result": existing,
    }

    output = graph.invoke(state, config={"configurable": {"thread_id": "source1"}})

    assert output["result"].triage.score == 90
    assert output["result"].digest.summary == "Already succeeded."
    assert call_log == ["triage"]
