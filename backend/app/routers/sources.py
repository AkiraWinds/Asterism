import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import get_data_root
from app.ingestion.extractor import extract_content
from app.ingestion.fetcher import (
    FetchBlockedError,
    FetchError,
    FetchTimeoutError,
    LoginRequiredError,
    fetch_url,
)
from app.ingestion.title import extract_title
from app.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderMissingError,
    ProviderTimeoutError,
)
from app.repositories.config_repository import ConfigError
from app.repositories.source_repository import (
    create_source,
    create_source_from_url,
    get_source,
    list_sources,
)
from app.schemas.agent import AgentErrorResponse
from app.schemas.source import (
    SourceCreateRequest,
    SourceDetailResponse,
    SourceSummaryResponse,
)

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)


def _error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=AgentErrorResponse(error_type=error_type, message=message).model_dump(),
    )


@router.post("", response_model=SourceDetailResponse)
def create_source_endpoint(payload: SourceCreateRequest):
    data_root = get_data_root()

    if payload.url:
        try:
            html = fetch_url(payload.url)
        except LoginRequiredError as exc:
            logger.warning("Ingestion login_required url=%s", payload.url)
            return _error_response(400, "login_required", str(exc))
        except FetchBlockedError as exc:
            logger.warning("Ingestion blocked url=%s", payload.url)
            return _error_response(400, "blocked", str(exc))
        except FetchTimeoutError as exc:
            logger.warning("Ingestion fetch timeout url=%s", payload.url)
            return _error_response(504, "timeout", str(exc))
        except FetchError as exc:
            logger.warning("Ingestion fetch error url=%s type=%s", payload.url, type(exc).__name__)
            return _error_response(502, "error", str(exc))

        title = extract_title(html, payload.url)

        try:
            content = extract_content(html, payload.url, data_root)
        except ConfigError as exc:
            return _error_response(400, "config", str(exc))
        except ProviderMissingError as exc:
            return _error_response(400, "missing", str(exc))
        except ProviderConfigError as exc:
            return _error_response(400, "config", str(exc))
        except ProviderTimeoutError as exc:
            logger.warning("Ingestion extraction provider timeout url=%s", payload.url)
            return _error_response(504, "timeout", str(exc))
        except ProviderError as exc:
            logger.warning(
                "Ingestion extraction provider error url=%s type=%s", payload.url, type(exc).__name__
            )
            return _error_response(502, "error", str(exc))

        try:
            record = create_source_from_url(data_root, payload.url, title, html, content)
        except OSError as exc:
            logger.exception("Failed to persist source for url=%s", payload.url)
            return _error_response(500, "storage", f"Failed to save source: {exc}")
        return SourceDetailResponse(
            id=record.id, title=record.title, created_at=record.created_at, content=record.content
        )

    if not payload.title or payload.content is None:
        raise HTTPException(
            status_code=400, detail="Both 'title' and 'content' are required when 'url' is not provided"
        )

    record = create_source(data_root, title=payload.title, content=payload.content)
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
