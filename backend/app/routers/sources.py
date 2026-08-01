"""API routes for creating, listing, and analyzing sources."""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.checkpoint.sqlite import SqliteSaver

from app.chat.prompts import build_chat_prompt
from app.concept_graph.pipeline import process_highlight, process_source_concepts, promote_concept
from app.core.config import get_data_root
from app.graph import build_system_graph, checkpoint_db_path
from app.graph_store.store import delete_concept_highlights_for_highlight, graph_db_path, init_db
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
from app.repositories.config_repository import ConfigError, load_brave_api_key, load_config, load_embeddings_api_key
from app.repositories.source_repository import (
    append_chat_turn,
    append_highlight,
    create_source,
    create_source_from_url,
    find_duplicate_highlight,
    get_source,
    list_sources,
    mark_feedback_promoted,
    read_analysis,
    read_chat,
    read_feedback,
    read_highlights,
    read_source_url,
    update_highlight_note,
    upsert_feedback,
    write_analysis,
)
from app.schemas.agent import AgentErrorResponse
from app.schemas.analysis import AnalysisResult, Concept
from app.schemas.chat import ChatHistory, ChatRequest, ChatTurn
from app.schemas.feedback import FeedbackEntry, FeedbackHistory, FeedbackRequest
from app.schemas.graph import HighlightProcessResult
from app.schemas.highlight import Highlight, HighlightCreateRequest, HighlightHistory, HighlightUpdateRequest
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

    # Auto-populate the concept graph from this analyze's digest concepts, same
    # ConfigError-caught-separately pattern as the highlights endpoints below:
    # a missing/invalid embeddings key surfaces via concept_graph_error rather
    # than blocking the (already-computed) digest/critique/claims results.
    if result.digest and result.digest.concepts:
        # Broad except is intentional here: _dedupe_and_insert only catches
        # (ValueError, ProviderError) internally, so anything else (e.g. a
        # locked graph.db raising sqlite3.OperationalError, or an unexpected
        # embed_text failure) must still be caught here rather than
        # propagate as an unhandled 500 — otherwise write_analysis below
        # never runs, and the already-computed digest/critique/claims work
        # gets stranded looking like "still Processing" (status is inferred
        # from file existence, not stored).
        try:
            llm_provider, embeddings_api_key, brave_api_key = _load_llm_and_embeddings(data_root)
            _, _, _, concept_graph_error = process_source_concepts(
                data_root, source_id, result.digest.concepts, llm_provider, embeddings_api_key,
                brave_api_key=brave_api_key,
            )
            result.concept_graph_error = concept_graph_error
        except Exception as exc:
            result.concept_graph_error = str(exc)

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


@router.get("/{source_id}/highlights", response_model=HighlightHistory)
def get_highlights_endpoint(source_id: str) -> HighlightHistory:
    data_root = get_data_root()
    if get_source(data_root, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return read_highlights(data_root, source_id)


def _load_llm_and_embeddings(data_root):
    """Returns (provider, embeddings_api_key, brave_api_key) or raises ConfigError."""
    config = load_config(data_root)
    embeddings_api_key = load_embeddings_api_key(data_root)
    brave_api_key = load_brave_api_key(data_root)
    return build_provider(config, data_root), embeddings_api_key, brave_api_key


@router.post("/{source_id}/highlights", response_model=HighlightProcessResult)
def post_highlight_endpoint(source_id: str, payload: HighlightCreateRequest):
    data_root = get_data_root()
    record = get_source(data_root, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Same source_quote + note pair already saved for this source (e.g. an
    # accidental double-submit from the UI): return it as-is rather than
    # creating a second highlights.json row and re-running the concept-graph
    # extraction pipeline, which would also add a duplicate provenance link.
    existing = find_duplicate_highlight(data_root, source_id, payload.source_quote, payload.note)
    if existing is not None:
        return HighlightProcessResult(highlight=existing, duplicate=True)

    highlight = Highlight(
        id=f"h_{uuid.uuid4().hex[:10]}",
        source_quote=payload.source_quote,
        note=payload.note,
        source_title=record.title,
        source_url=read_source_url(data_root, source_id),
        created_at=_now_iso(),
    )
    # The highlight itself always persists, even if extraction below fails —
    # a saved highlight with a failed extraction is a visible, valid state
    # (extraction_error in the response), never a silently-dropped one.
    append_highlight(data_root, source_id, highlight)

    try:
        llm_provider, embeddings_api_key, brave_api_key = _load_llm_and_embeddings(data_root)
    except ConfigError as exc:
        return HighlightProcessResult(highlight=highlight, extraction_error=str(exc))

    return process_highlight(data_root, source_id, highlight, llm_provider, embeddings_api_key, brave_api_key=brave_api_key)


@router.patch("/{source_id}/highlights/{highlight_id}", response_model=HighlightProcessResult)
def patch_highlight_endpoint(source_id: str, highlight_id: str, payload: HighlightUpdateRequest):
    data_root = get_data_root()
    if get_source(data_root, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")

    updated = update_highlight_note(data_root, source_id, highlight_id, payload.note)
    if updated is None:
        raise HTTPException(status_code=404, detail="Highlight not found")

    # A changed note is a new signal worth re-processing (Decision 6): clear this
    # highlight's old provenance links first so re-extraction starts clean,
    # rather than accumulating links to concepts its previous note produced.
    # init_db is called here too (not just inside process_highlight below)
    # because the original POST may have hit a ConfigError before ever reaching
    # process_highlight, leaving graph.db uninitialized — this delete would
    # otherwise fail with "no such table" on that path.
    db_path = graph_db_path(data_root)
    init_db(db_path)
    delete_concept_highlights_for_highlight(db_path, highlight_id)

    try:
        llm_provider, embeddings_api_key, brave_api_key = _load_llm_and_embeddings(data_root)
    except ConfigError as exc:
        return HighlightProcessResult(highlight=updated, extraction_error=str(exc))

    return process_highlight(data_root, source_id, updated, llm_provider, embeddings_api_key, brave_api_key=brave_api_key)


@router.get("/{source_id}/feedback", response_model=FeedbackHistory)
def get_feedback_endpoint(source_id: str) -> FeedbackHistory:
    data_root = get_data_root()
    if get_source(data_root, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return read_feedback(data_root, source_id)


@router.put("/{source_id}/feedback", response_model=FeedbackEntry)
def put_feedback_endpoint(source_id: str, payload: FeedbackRequest) -> FeedbackEntry:
    data_root = get_data_root()
    if get_source(data_root, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return upsert_feedback(
        data_root, source_id, kind=payload.kind, section=payload.section,
        content=payload.content, term=payload.term, rating=payload.rating,
    )


@router.post("/{source_id}/feedback/{feedback_id}/promote", response_model=HighlightProcessResult)
def promote_feedback_endpoint(source_id: str, feedback_id: str):
    data_root = get_data_root()
    record = get_source(data_root, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")

    entry = next((e for e in read_feedback(data_root, source_id).entries if e.id == feedback_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Feedback entry not found")
    if entry.rating != "up":
        raise HTTPException(status_code=400, detail="Feedback entry must be thumbs-up before promoting")
    if entry.promoted:
        raise HTTPException(status_code=400, detail="Feedback entry already promoted")

    # Same reuse-vs-reprocess precedent as post_highlight_endpoint: if this
    # feedback's content exactly matches an already-saved highlight, that
    # highlight has already been through the concept-graph pipeline (or its
    # failure is already reflected in graph.db's provenance). Re-running
    # process_highlight/promote_concept here would call link_concept_highlight
    # again for the same (concept_id, source_id, highlight_id) — concept_highlights
    # has no unique constraint, so that's a silent duplicate provenance row at
    # best, and a genuine duplicate concept node at worst if the LLM dedup judge
    # nondeterministically returns "new" on a second call with identical input.
    existing_highlight = find_duplicate_highlight(data_root, source_id, entry.content, note=None)
    if existing_highlight is not None:
        mark_feedback_promoted(data_root, source_id, feedback_id)
        return HighlightProcessResult(highlight=existing_highlight, duplicate=True)

    highlight = Highlight(
        id=f"h_{uuid.uuid4().hex[:10]}",
        source_quote=entry.content,
        note=None,
        source_title=record.title,
        source_url=read_source_url(data_root, source_id),
        created_at=_now_iso(),
    )
    append_highlight(data_root, source_id, highlight)

    # The highlight always persists (and feedback is marked promoted below)
    # regardless of what happens next — matches post_highlight_endpoint's
    # existing "the highlight itself always persists even if extraction
    # fails" precedent. Promoting is a one-way user action; a downstream
    # provider hiccup shouldn't leave the button re-offering "promote" forever.
    try:
        llm_provider, embeddings_api_key, brave_api_key = _load_llm_and_embeddings(data_root)
    except ConfigError as exc:
        mark_feedback_promoted(data_root, source_id, feedback_id)
        return HighlightProcessResult(highlight=highlight, extraction_error=str(exc))

    if entry.kind == "concept":
        concept = Concept(id="promoted", term=entry.term, definition=entry.content)
        result = promote_concept(
            data_root, source_id, highlight, concept, llm_provider, embeddings_api_key, brave_api_key=brave_api_key
        )
    else:
        result = process_highlight(
            data_root, source_id, highlight, llm_provider, embeddings_api_key, brave_api_key=brave_api_key
        )

    mark_feedback_promoted(data_root, source_id, feedback_id)
    return result
