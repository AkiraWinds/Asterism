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
    golden: bool = False


class Edge(BaseModel):
    id: str
    from_id: str
    to_id: str
    type: Literal["related", "contradicts", "extends"]
    summary: str


class GraphNode(BaseModel):
    """One node in the GET /graph response — a concept, a source, or a wiki
    page/aspect. Distinct from ConceptNode (above): ConceptNode is the
    per-highlight-processing result type used by POST /sources/{id}/highlights
    and is unrelated to this endpoint. See
    docs/superpowers/specs/2026-09-10-graph-multi-entity-view-design.md.
    """

    id: str
    kind: Literal["concept", "source", "wiki"]
    term: str
    definition: str | None = None  # concept-only
    self_relevant: bool = False    # concept-only
    golden: bool = False           # concept-only
    is_aspect: bool = False        # wiki-only: True for an aspect sub-page node


class GraphEdge(BaseModel):
    """One edge in the GET /graph response. `type` (related/contradicts/
    extends) is set only when kind == 'concept_relation'; the three
    structural edge kinds (source_link/wiki_link/aspect_link) leave it None."""

    id: str
    from_id: str
    to_id: str
    kind: Literal["concept_relation", "source_link", "wiki_link", "aspect_link"]
    type: str | None = None
    summary: str = ""


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ReviewQueueEntry(BaseModel):
    id: str
    candidate_concept_id: str
    existing_concept_id: str
    llm_judgment: str
    proposed_edge_type: Literal["related", "contradicts", "extends"] = "related"
    created_at: str


class ReviewQueueResolveRequest(BaseModel):
    action: Literal["merge", "keep_separate"]


class HighlightProcessResult(BaseModel):
    highlight: Highlight
    concepts: list[ConceptNode] = []
    edges: list[Edge] = []
    queued: list[ReviewQueueEntry] = []
    extraction_error: str | None = None
    # True when this POST matched an existing highlight (same source_quote + note
    # in this source) and returned it as-is instead of creating a new one — see
    # find_duplicate_highlight in source_repository.py. concepts/edges/queued are
    # left empty in this case since no new extraction ran.
    duplicate: bool = False
