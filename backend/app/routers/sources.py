"""API routes for creating, listing, and analyzing sources."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.checkpoint.sqlite import SqliteSaver

from app.chat.prompts import build_chat_prompt
from app.core.config import get_data_root
from app.graph import build_system_graph, checkpoint_db_path
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
from app.providers.factory import build_provider
from app.repositories.config_repository import ConfigError, load_config
from app.repositories.source_repository import (
    append_chat_turn,
    create_source,
    create_source_from_url,
    get_source,
    list_sources,
    read_analysis,
    read_chat,
    write_analysis,
)
from app.schemas.agent import AgentErrorResponse
from app.schemas.analysis import AnalysisResult
from app.schemas.chat import ChatHistory, ChatRequest, ChatTurn
from app.schemas.source import (
    SourceCreateRequest,
    SourceDetailResponse,
    SourceSummaryResponse,
)

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        # A freshly ingested source has never been analyzed yet, so analysis is None.
        return SourceDetailResponse(
            id=record.id, title=record.title, created_at=record.created_at, content=record.content, analysis=None
        )

    if not payload.title or payload.content is None:
        raise HTTPException(
            status_code=400, detail="Both 'title' and 'content' are required when 'url' is not provided"
        )

    record = create_source(data_root, title=payload.title, content=payload.content)
    return SourceDetailResponse(
        id=record.id, title=record.title, created_at=record.created_at, content=record.content, analysis=None
    )


@router.get("", response_model=list[SourceSummaryResponse])
def list_sources_endpoint() -> list[SourceSummaryResponse]:
    records = list_sources(get_data_root())
    return [
        SourceSummaryResponse(id=r.id, title=r.title, created_at=r.created_at) for r in records
    ]


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source_endpoint(source_id: str) -> SourceDetailResponse:
    data_root = get_data_root()
    record = get_source(data_root, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    # analysis.json may not exist yet (source never analyzed) or may hold a
    # partial result (some fields failed) — read_analysis returns None or an
    # AnalysisResult with the *_error fields set accordingly in either case.
    analysis = read_analysis(data_root, source_id)
    return SourceDetailResponse(
        id=record.id, title=record.title, created_at=record.created_at, content=record.content, analysis=analysis
    )


@router.post("/{source_id}/analyze", response_model=AnalysisResult)
def analyze_source_endpoint(source_id: str):
    data_root = get_data_root()

    record = get_source(data_root, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Config errors (e.g. missing/invalid config.json) are a client-fixable
    # setup problem distinct from in-graph analysis failures below, so they're
    # caught separately and reported as 400s before any graph work starts.
    try:
        config = load_config(data_root)
    except ConfigError as exc:
        return _error_response(400, "config", str(exc))

    # Seed the graph with any previously-saved partial result so a retry only
    # recomputes fields that are still missing/errored (see app/graph.py's
    # _analyze_node, which copies these into the analysis subgraph's input).
    existing = read_analysis(data_root, source_id)
    db_path = checkpoint_db_path(data_root)

    # The checkpointer is a context manager scoped to just this request: it
    # opens a sqlite connection for the duration of the graph run and closes
    # it before the response is returned, rather than holding a
    # connection open for the process lifetime.
    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        graph = build_system_graph(checkpointer)
        state = {
            "source_id": source_id,
            "title": record.title,
            "content": record.content,
            "data_root": data_root,
            "config": config,
            "result": existing,
        }
        # thread_id=source_id ties this run's checkpoints to the source, so a
        # later retry for the same source resumes from its own saved state.
        # ProviderMissingError/ProviderConfigError are pre-graph "hard stop"
        # failures per spec: they're config-level problems (CLI not on PATH,
        # bad API key) that no retry inside the graph can fix, so they're
        # caught here and mapped to a 400 instead of letting the graph write
        # an all-null "Ready" analysis.json (see app/analysis/nodes.py's
        # _complete_with_retry, which re-raises these without retrying).
        try:
            output = graph.invoke(state, config={"configurable": {"thread_id": source_id}})
        except ProviderMissingError as exc:
            return _error_response(400, "missing", str(exc))
        except ProviderConfigError as exc:
            return _error_response(400, "config", str(exc))

    result = output["result"]
    write_analysis(data_root, source_id, result)
    return result


@router.get("/{source_id}/chat", response_model=ChatHistory)
def get_chat_endpoint(source_id: str) -> ChatHistory:
    data_root = get_data_root()
    if get_source(data_root, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return read_chat(data_root, source_id)


@router.post("/{source_id}/chat")
def post_chat_endpoint(source_id: str, payload: ChatRequest):
    data_root = get_data_root()
    record = get_source(data_root, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Only a missing config.json can be checked before the SSE response starts.
    # ProviderMissingError/ProviderConfigError only actually raise once
    # stream_complete() is called, which happens lazily inside the generator
    # below — by then the response's 200 status is already committed, so
    # those surface as a mid-stream `event: error` frame instead (see
    # docs/superpowers/specs/2026-07-29-chat-copilot-design.md Error Handling).
    try:
        config = load_config(data_root)
    except ConfigError as exc:
        return _error_response(400, "config", str(exc))

    provider = build_provider(config, data_root)
    analysis = read_analysis(data_root, source_id)
    history = read_chat(data_root, source_id)
    now = _now_iso()

    prompt = build_chat_prompt(
        content=record.content,
        analysis=analysis,
        history=history.turns,
        attached_highlight=payload.attached_highlight,
        message=payload.message,
    )

    append_chat_turn(
        data_root,
        source_id,
        ChatTurn(
            role="user",
            content=payload.message,
            attached_highlight=payload.attached_highlight,
            created_at=now,
        ),
    )

    def event_stream():
        collected = ""
        try:
            for chunk in provider.stream_complete(prompt):
                collected += chunk
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except ProviderError as exc:
            logger.warning(
                "Chat stream provider error source_id=%s type=%s", source_id, type(exc).__name__
            )
            append_chat_turn(
                data_root,
                source_id,
                ChatTurn(role="assistant", content=collected, truncated=True, created_at=_now_iso()),
            )
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            return

        append_chat_turn(
            data_root,
            source_id,
            ChatTurn(role="assistant", content=collected, created_at=_now_iso()),
        )
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
