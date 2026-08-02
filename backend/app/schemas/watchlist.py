"""Pydantic models for the user-seeded entity watchlist (Phase 6, decision 8):
you declare a term you care about, the resolution chain in
app/watchlist/resolver.py drafts a definition (graph match, web search, or
LLM reasoning), and you approve or reject it. See
docs/superpowers/specs/2026-08-01-entity-extraction-reference-lookup-design.md.
"""

from typing import Literal

from pydantic import BaseModel


class WatchlistEntry(BaseModel):
    id: str
    term: str
    status: Literal["pending", "resolved", "rejected"]
    # Set by the resolver when it drafts a fresh definition (web search or LLM
    # reasoning branch); left None when draft_matched_concept_id is set instead
    # (the term matched an existing graph concept, so no new definition exists).
    draft_definition: str | None = None
    # Set by the resolver when the term matched an existing graph concept
    # closely enough to reuse rather than draft fresh.
    draft_matched_concept_id: str | None = None
    # Set only after approval — the concept this entry ultimately resolved to,
    # whether newly created or an existing one flagged golden.
    resolved_concept_id: str | None = None
    created_at: str
    updated_at: str


class WatchlistCreateRequest(BaseModel):
    term: str


class WatchlistHistory(BaseModel):
    entries: list[WatchlistEntry] = []
