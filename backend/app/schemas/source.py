"""API request/response schemas for the /sources endpoints."""

from pydantic import BaseModel

from app.schemas.analysis import AnalysisResult, Triage


class SourceCreateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    url: str | None = None
    html: str | None = None


class TriagePreviewResponse(BaseModel):
    duplicate: bool
    id: str | None = None
    title: str | None = None
    triage: Triage | None = None


class SourceSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str
    read_at: str | None = None


class SourcePreviewResponse(BaseModel):
    """Lightweight preview for the graph view's source-node side panel.

    For html sources this is the AI digest summary (or a fallback if not yet
    analyzed); for text sources it's the raw note content itself, since
    summarizing an already-concise user note adds no value.
    """

    id: str
    title: str
    type: str
    preview_text: str


class SourceDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    content: str
    analysis: AnalysisResult | None = None
    read_at: str | None = None
    # True when this response is an already-existing source returned in place
    # of creating a new one (see find_duplicate_source in create_source_endpoint),
    # not a freshly ingested source.
    duplicate: bool = False
