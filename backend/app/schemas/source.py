"""API request/response schemas for the /sources endpoints."""

from pydantic import BaseModel

from app.schemas.analysis import AnalysisResult


class SourceCreateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    url: str | None = None
    html: str | None = None


class SourceSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str


class SourceDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    content: str
    analysis: AnalysisResult | None = None
