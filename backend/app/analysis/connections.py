"""
Claim-level connection finder and analysis finalizer.

Implements a two-phase process to find connections between claims across analyzed sources:
1. Coarse filtering: use LLM to identify candidate sources most relevant to the current analysis
2. Detailed comparison: use LLM to extract specific claim-level relationships (contradicts, supports, etc.)

Then assembles the final AnalysisResult from all analysis phases.
"""

from datetime import datetime, timezone

from app.analysis.parsing import NodeOutputError, extract_json
from app.analysis.prompts import build_coarse_filter_prompt, build_detailed_compare_prompt
from app.analysis.state import AnalysisState
from app.providers.base import ProviderError
from app.providers.factory import build_provider
from app.repositories.source_repository import list_analysis_claims, list_analysis_summaries
from app.schemas.analysis import AnalysisResult, Connection

MAX_CANDIDATES = 5


def find_connections(state: AnalysisState) -> dict:
    # Early exit: need both digest and claims to find connections
    digest = state.get("digest")
    claims = state.get("claims")
    if digest is None or not claims:
        return {"connections": []}

    data_root = state["data_root"]
    source_id = state["source_id"]
    summaries = list_analysis_summaries(data_root, exclude_id=source_id)
    if not summaries:
        return {"connections": []}

    provider = build_provider(state["config"], data_root)

    # Phase 1: Coarse filtering - identify candidate sources
    coarse_prompt = build_coarse_filter_prompt(state["title"], digest.summary, summaries)
    try:
        coarse_data = extract_json(provider.complete(coarse_prompt))
        candidate_ids = [c for c in coarse_data.get("candidate_ids", []) if isinstance(c, str)][:MAX_CANDIDATES]
    except (ProviderError, NodeOutputError):
        return {"connections": []}

    if not candidate_ids:
        return {"connections": []}

    # Fetch detailed claims from candidate sources
    candidates = list_analysis_claims(data_root, candidate_ids)
    if not candidates:
        return {"connections": []}

    # Phase 2: Detailed comparison - extract specific claim relationships
    detailed_prompt = build_detailed_compare_prompt(source_id, claims, candidates)
    try:
        detailed_data = extract_json(provider.complete(detailed_prompt))
        raw_connections = detailed_data.get("connections", [])
    except (ProviderError, NodeOutputError):
        return {"connections": []}

    # Convert raw data to Connection objects
    connections = []
    for i, item in enumerate(raw_connections):
        try:
            connections.append(Connection(**{**item, "id": f"conn{i + 1}"}))
        except TypeError:
            # Skip malformed connection data
            continue
    return {"connections": connections}


def finalize(state: AnalysisState) -> dict:
    # Assemble final AnalysisResult from all analysis phases
    result = AnalysisResult(
        triage=state.get("triage"),
        triage_error=state.get("triage_error"),
        digest=state.get("digest"),
        digest_error=state.get("digest_error"),
        critique=state.get("critique"),
        critique_error=state.get("critique_error"),
        claims=state.get("claims"),
        claims_error=state.get("claims_error"),
        connections=state.get("connections", []),
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
    return {"result": result}
