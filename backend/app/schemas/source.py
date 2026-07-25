from pydantic import BaseModel


class SourceCreateRequest(BaseModel):
    title: str
    content: str


class SourceSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str


class SourceDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    content: str
