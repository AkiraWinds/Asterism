"""Analysis state TypedDict for tracking the processing pipeline."""

from pathlib import Path
from typing import TypedDict

from app.repositories.config_repository import AgentConfig
from app.schemas.analysis import Claim, Connection, Critique, Digest, Triage


class AnalysisState(TypedDict, total=False):
    source_id: str
    title: str
    content: str
    source_url: str | None
    data_root: Path
    config: AgentConfig
    triage: Triage | None
    triage_error: str | None
    digest: Digest | None
    digest_error: str | None
    critique: Critique | None
    critique_error: str | None
    claims: list[Claim] | None
    claims_error: str | None
    connections: list[Connection]
