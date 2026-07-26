from typing import Literal

from pydantic import BaseModel


class Highlight(BaseModel):
    id: str
    text: str
    type: Literal["insight", "fact", "actionable"]
    source_quote: str


class Concept(BaseModel):
    id: str
    term: str
    definition: str


class Triage(BaseModel):
    score: int
    action: Literal["must_read", "worth_reading", "skim", "summary_only", "skip"]
    reason: str
    read_time_minutes: int
    density: int
    originality: int


class Digest(BaseModel):
    summary: str
    highlights: list[Highlight] = []
    concepts: list[Concept] = []
    structure: list[str] = []


class Critique(BaseModel):
    hidden_assumptions: list[str] = []
    potential_issues: list[str] = []
    needs_verification: list[str] = []
    bias_indicators: list[str] = []


class Claim(BaseModel):
    id: str
    text: str
    type: Literal["factual", "opinion", "prediction"]
    source_quote: str


class Connection(BaseModel):
    id: str
    type: Literal["redundant", "contradicts", "related"]
    summary: str
    details: str
    related_source_ids: list[str] = []
    claim_refs: list[str] = []


class AnalysisResult(BaseModel):
    triage: Triage | None = None
    triage_error: str | None = None
    digest: Digest | None = None
    digest_error: str | None = None
    critique: Critique | None = None
    critique_error: str | None = None
    claims: list[Claim] | None = None
    claims_error: str | None = None
    connections: list[Connection] = []
    analyzed_at: str
