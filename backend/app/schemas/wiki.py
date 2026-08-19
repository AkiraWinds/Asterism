"""Pydantic models for the read-only wiki-page API (GET /wiki/pages/...),
which lets the frontend display already-compiled wiki pages next to the
concept graph. See docs/superpowers/specs/2026-08-19-graph-wiki-panel-design.md.
"""

from pydantic import BaseModel


class WikiPageAspect(BaseModel):
    slug: str
    term: str


class WikiPageResponse(BaseModel):
    slug: str
    term: str
    updated_at: str
    body: str
    aspects: list[WikiPageAspect] = []
