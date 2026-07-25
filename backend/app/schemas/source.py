from pydantic import BaseModel


class SourceCreateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    url: str | None = None


class SourceSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str


class SourceDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    content: str
