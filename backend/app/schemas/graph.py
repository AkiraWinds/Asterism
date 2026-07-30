"""Pydantic models for Phase 6b's concept graph: ConceptNode/Edge (the graph
itself), ReviewQueueEntry (medium-confidence dedup candidates awaiting user
decision), and HighlightProcessResult (the response shape for
POST /sources/{id}/highlights). See
docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md.
"""

from typing import Literal

from pydantic import BaseModel

from app.schemas.highlight import Highlight


class ConceptNode(BaseModel):
    id: str
    term: str
    definition: str
    self_relevant: bool = False


class Edge(BaseModel):
    id: str
    from_id: str
    to_id: str
    type: Literal["related", "contradicts", "extends"]
    summary: str


class GraphResponse(BaseModel):
    nodes: list[ConceptNode]
    edges: list[Edge]


class ReviewQueueEntry(BaseModel):
    id: str
    candidate_concept_id: str
    existing_concept_id: str
    llm_judgment: str
    created_at: str


class ReviewQueueResolveRequest(BaseModel):
    action: Literal["merge", "keep_separate"]


class HighlightProcessResult(BaseModel):
    highlight: Highlight
    concepts: list[ConceptNode] = []
    edges: list[Edge] = []
    queued: list[ReviewQueueEntry] = []
    extraction_error: str | None = None
