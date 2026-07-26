from unittest.mock import MagicMock

from app.analysis.connections import find_connections, finalize
from app.repositories.config_repository import AgentConfig
from app.repositories.source_repository import create_source, write_analysis
from app.schemas.analysis import AnalysisResult, Claim, Critique, Digest, Triage


def _base_state(tmp_path, source_id):
    return {
        "source_id": source_id,
        "title": "New Article",
        "content": "content",
        "data_root": tmp_path,
        "config": AgentConfig(strategy="api-key", provider="anthropic", api_key="fake"),
        "digest": Digest(summary="A summary about RAG."),
        "claims": [Claim(id="claim1", text="RAG reduces hallucination", type="factual", source_quote="x")],
    }


def test_find_connections_returns_empty_when_digest_or_claims_missing(tmp_path):
    state = _base_state(tmp_path, "new-source")
    state["claims"] = None

    result = find_connections(state)

    assert result == {"connections": []}


def test_find_connections_returns_empty_when_library_has_no_analyzed_sources(tmp_path):
    state = _base_state(tmp_path, "new-source")

    result = find_connections(state)

    assert result == {"connections": []}


def test_find_connections_full_two_phase_flow(tmp_path, monkeypatch):
    existing = create_source(tmp_path, title="Old Article", content="Body")
    write_analysis(
        tmp_path,
        existing.id,
        AnalysisResult(
            digest=Digest(summary="Old article about RAG."),
            claims=[Claim(id="claim1", text="RAG does not eliminate hallucination", type="factual", source_quote="y")],
            analyzed_at="2026-07-26T12:00:00+00:00",
        ),
    )

    coarse_provider_response = f'{{"candidate_ids": ["{existing.id}"]}}'
    detailed_provider_response = (
        '{"connections": [{"type": "contradicts", "summary": "Disagree on RAG.", '
        '"details": "One says RAG reduces hallucination, the other says it does not.", '
        f'"related_source_ids": ["{existing.id}"], "claim_refs": ["claim1", "{existing.id}:claim1"]}}]}}'
    )
    provider = MagicMock()
    provider.complete.side_effect = [coarse_provider_response, detailed_provider_response]
    monkeypatch.setattr("app.analysis.connections.build_provider", lambda config, data_root: provider)

    state = _base_state(tmp_path, "new-source")
    result = find_connections(state)

    assert len(result["connections"]) == 1
    connection = result["connections"][0]
    assert connection.id == "conn1"
    assert connection.type == "contradicts"
    assert connection.related_source_ids == [existing.id]


def test_finalize_assembles_analysis_result_with_partial_failure():
    state = {
        "triage": Triage(score=78, action="worth_reading", reason="x", read_time_minutes=5, density=70, originality=60),
        "triage_error": None,
        "digest": None,
        "digest_error": "provider timeout",
        "critique": Critique(),
        "critique_error": None,
        "claims": None,
        "claims_error": "provider timeout",
        "connections": [],
    }

    result = finalize(state)

    analysis = result["result"]
    assert analysis.triage.score == 78
    assert analysis.digest is None
    assert analysis.digest_error == "provider timeout"
    assert analysis.analyzed_at
