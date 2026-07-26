from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import pytest

from app.main import app
from app.providers.base import ProviderConfigError, ProviderError, ProviderMissingError

client = TestClient(app)


def _create_source() -> str:
    response = client.post("/sources", json={"title": "Test", "content": "Some content about RAG."})
    return response.json()["id"]


def _fake_provider(responses: dict[str, str]):
    """responses maps a substring of the prompt to the canned response for that call.

    The analysis subgraph fans out to triage/digest/critique/claims in parallel
    from START (see app/analysis/graph.py's add_edge(START, ...) calls), so
    there is no guaranteed call order. A positional side_effect list would be
    unsound and intermittently fail; matching on a distinctive prompt marker
    per node is order-independent. Mirrors the helper in test_analysis_graph.py.
    """
    provider = MagicMock()

    def _complete(prompt: str) -> str:
        for marker, response in responses.items():
            if marker in prompt:
                return response
        raise AssertionError(f"No canned response configured for prompt: {prompt[:200]}")

    provider.complete.side_effect = _complete
    return provider


def test_analyze_full_success(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')
    source_id = _create_source()

    provider = _fake_provider(
        {
            "Score how much attention": '{"score": 78, "action": "worth_reading", "reason": "x", "read_time_minutes": 5, "density": 70, "originality": 60}',
            "Summarize this content": '{"summary": "A summary.", "highlights": [], "concepts": [], "structure": []}',
            "Critically evaluate": '{"hidden_assumptions": [], "potential_issues": [], "needs_verification": [], "bias_indicators": []}',
            "Extract up to 8": '{"claims": []}',
        }
    )
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    response = client.post(f"/sources/{source_id}/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["triage"]["score"] == 78
    assert body["digest"]["summary"] == "A summary."

    get_response = client.get(f"/sources/{source_id}")
    assert get_response.json()["analysis"]["triage"]["score"] == 78


def test_analyze_partial_failure_returns_200_with_null_field(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')
    source_id = _create_source()

    def _complete(prompt: str) -> str:
        if "Extract up to 8" in prompt:
            raise ProviderError("boom")
        if "Score how much attention" in prompt:
            return '{"score": 78, "action": "worth_reading", "reason": "x", "read_time_minutes": 5, "density": 70, "originality": 60}'
        if "Summarize this content" in prompt:
            return '{"summary": "A summary.", "highlights": [], "concepts": [], "structure": []}'
        if "Critically evaluate" in prompt:
            return '{"hidden_assumptions": [], "potential_issues": [], "needs_verification": [], "bias_indicators": []}'
        raise AssertionError(f"No canned response configured for prompt: {prompt[:200]}")

    provider = MagicMock()
    provider.complete.side_effect = _complete
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    response = client.post(f"/sources/{source_id}/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["triage"]["score"] == 78
    assert body["claims"] is None
    assert body["claims_error"] is not None


@pytest.mark.parametrize(
    ("error_cls", "expected_error_type"),
    [(ProviderMissingError, "missing"), (ProviderConfigError, "config")],
)
def test_analyze_provider_setup_error_returns_400_and_writes_no_analysis(
    tmp_path: Path, monkeypatch, error_cls, expected_error_type
):
    # A provider that's unusable (CLI not on PATH, bad API key) is a pre-graph
    # "hard stop" per spec: it must be reported as a 400, and must NOT result
    # in an all-null analysis.json being written (which would read as "Ready"
    # under this repo's file-existence status model).
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')
    source_id = _create_source()

    provider = MagicMock()
    provider.complete.side_effect = error_cls("provider unusable")
    monkeypatch.setattr("app.analysis.nodes.build_provider", lambda config, data_root: provider)

    response = client.post(f"/sources/{source_id}/analyze")

    assert response.status_code == 400
    assert response.json()["error_type"] == expected_error_type

    analysis_path = tmp_path / "library" / source_id / "analysis.json"
    assert not analysis_path.exists()


def test_analyze_missing_config_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.post(f"/sources/{source_id}/analyze")

    assert response.status_code == 400
    assert response.json()["error_type"] == "config"


def test_analyze_missing_source_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')

    response = client.post("/sources/does-not-exist/analyze")

    assert response.status_code == 404
