"""Pydantic models for per-point analysis feedback: the shape of feedback.json.
A FeedbackEntry rates one Digest Concept, Claim, or Critique item and optionally
tracks whether it's been promoted into the concept graph. Matched to analysis
items by exact content (kind, section, content), not by analysis.json's ids —
those are reassigned on every reanalyze, content is the only stable handle.
See docs/superpowers/specs/2026-08-01-analysis-feedback-promote-design.md.
"""

from typing import Literal

from pydantic import BaseModel, model_validator


class FeedbackEntry(BaseModel):
    id: str
    kind: Literal["concept", "claim", "critique"]
    section: str | None = None
    content: str
    term: str | None = None
    rating: Literal["up", "down"]
    promoted: bool = False
    promoted_at: str | None = None
    created_at: str
    updated_at: str


class FeedbackHistory(BaseModel):
    entries: list[FeedbackEntry] = []


class FeedbackRequest(BaseModel):
    kind: Literal["concept", "claim", "critique"]
    section: str | None = None
    content: str
    term: str | None = None
    rating: Literal["up", "down"]

    @model_validator(mode="after")
    def _validate_kind_specific_fields(self) -> "FeedbackRequest":
        if self.kind == "critique" and self.section is None:
            raise ValueError("section is required when kind is 'critique'")
        if self.kind != "critique" and self.section is not None:
            raise ValueError("section is only valid when kind is 'critique'")
        if self.kind == "concept" and self.term is None:
            raise ValueError("term is required when kind is 'concept'")
        return self
