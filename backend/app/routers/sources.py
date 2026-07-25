from fastapi import APIRouter, HTTPException

from app.core.config import get_data_root
from app.repositories.source_repository import create_source, get_source, list_sources
from app.schemas.source import (
    SourceCreateRequest,
    SourceDetailResponse,
    SourceSummaryResponse,
)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", response_model=SourceDetailResponse)
def create_source_endpoint(payload: SourceCreateRequest) -> SourceDetailResponse:
    record = create_source(get_data_root(), title=payload.title, content=payload.content)
    return SourceDetailResponse(
        id=record.id, title=record.title, created_at=record.created_at, content=record.content
    )


@router.get("", response_model=list[SourceSummaryResponse])
def list_sources_endpoint() -> list[SourceSummaryResponse]:
    records = list_sources(get_data_root())
    return [
        SourceSummaryResponse(id=r.id, title=r.title, created_at=r.created_at) for r in records
    ]


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source_endpoint(source_id: str) -> SourceDetailResponse:
    record = get_source(get_data_root(), source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceDetailResponse(
        id=record.id, title=record.title, created_at=record.created_at, content=record.content
    )
