"""Parallel analysis node functions for triage, digest, critique, and claims extraction."""

from pydantic import ValidationError

from app.analysis.parsing import NodeOutputError, extract_json
from app.analysis.prompts import (
    build_claims_prompt,
    build_critique_prompt,
    build_digest_prompt,
    build_triage_prompt,
)
from app.analysis.state import AnalysisState
from app.providers.base import ProviderError
from app.providers.factory import build_provider
from app.schemas.analysis import Claim, Concept, Critique, Digest, Highlight, Triage

MAX_CONTENT_CHARS = 20_000
MAX_ATTEMPTS = 2


def _complete_with_retry(state: AnalysisState, prompt: str) -> dict:
    """Call LLM provider with retry logic; raise NodeOutputError if all attempts fail."""
    provider = build_provider(state["config"], state["data_root"])
    last_error = "unknown error"
    for _ in range(MAX_ATTEMPTS):
        try:
            response = provider.complete(prompt)
            return extract_json(response)
        except (ProviderError, NodeOutputError) as exc:
            # Retry on error, store the error to report if all attempts fail
            last_error = str(exc)
    raise NodeOutputError(last_error)


def run_triage(state: AnalysisState) -> dict:
    """Extract triage metadata (score, action, read time, etc.) from content."""
    # Skip if already populated
    if state.get("triage") is not None:
        return {}
    prompt = build_triage_prompt(state["title"], state["content"][:MAX_CONTENT_CHARS])
    try:
        data = _complete_with_retry(state, prompt)
        triage = Triage.model_validate(data)
    except (NodeOutputError, ValidationError) as exc:
        return {"triage": None, "triage_error": str(exc)}
    return {"triage": triage, "triage_error": None}


def run_digest(state: AnalysisState) -> dict:
    """Extract summary, highlights, and concepts from content."""
    # Skip if already populated
    if state.get("digest") is not None:
        return {}
    prompt = build_digest_prompt(state["title"], state["content"][:MAX_CONTENT_CHARS])
    try:
        data = _complete_with_retry(state, prompt)
        highlights = [
            Highlight(id=f"h{i + 1}", **item) for i, item in enumerate(data.get("highlights", []))
        ]
        concepts = [Concept(id=f"c{i + 1}", **item) for i, item in enumerate(data.get("concepts", []))]
        digest = Digest(
            summary=data.get("summary", ""),
            highlights=highlights,
            concepts=concepts,
            structure=data.get("structure", []),
        )
    except (NodeOutputError, ValidationError, TypeError) as exc:
        return {"digest": None, "digest_error": str(exc)}
    return {"digest": digest, "digest_error": None}


def run_critique(state: AnalysisState) -> dict:
    """Extract critique analysis (assumptions, issues, verification needs, bias) from content."""
    # Skip if already populated
    if state.get("critique") is not None:
        return {}
    prompt = build_critique_prompt(state["title"], state["content"][:MAX_CONTENT_CHARS])
    try:
        data = _complete_with_retry(state, prompt)
        critique = Critique.model_validate(data)
    except (NodeOutputError, ValidationError) as exc:
        return {"critique": None, "critique_error": str(exc)}
    return {"critique": critique, "critique_error": None}


def run_claims(state: AnalysisState) -> dict:
    """Extract factual claims from content."""
    # Skip if already populated
    if state.get("claims") is not None:
        return {}
    prompt = build_claims_prompt(state["title"], state["content"][:MAX_CONTENT_CHARS])
    try:
        data = _complete_with_retry(state, prompt)
        claims = [Claim(id=f"claim{i + 1}", **item) for i, item in enumerate(data.get("claims", []))]
    except (NodeOutputError, ValidationError, TypeError) as exc:
        return {"claims": None, "claims_error": str(exc)}
    return {"claims": claims, "claims_error": None}
