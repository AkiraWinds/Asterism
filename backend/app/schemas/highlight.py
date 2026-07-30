"""Pydantic models for Phase 6b user highlights: the shape of highlights.json
(Highlight, HighlightHistory) and the highlight-creation/update request bodies.
See docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md.
"""

from pydantic import BaseModel


class Highlight(BaseModel):
    id: str
    source_quote: str
    note: str | None = None
    # Denormalized from the source's meta.json at creation time — safe to copy
    # once since meta.json is immutable (CLAUDE.md's data model: written once
    # at capture, never modified). Lets any consumer (concept graph view,
    # review queue) show "from: <title>, read full article" without a second
    # lookup back to the source directory.
    source_title: str
    source_url: str | None = None
    created_at: str


class HighlightHistory(BaseModel):
    highlights: list[Highlight] = []


class HighlightCreateRequest(BaseModel):
    source_quote: str
    note: str | None = None


class HighlightUpdateRequest(BaseModel):
    note: str | None
