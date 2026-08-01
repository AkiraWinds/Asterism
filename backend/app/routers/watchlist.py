"""API routes for the user-seeded entity watchlist (Phase 6, decision 8):
CRUD over watchlist entries plus approve/reject actions that turn a resolved
draft into a golden concept. See
docs/superpowers/specs/2026-08-01-entity-extraction-reference-lookup-design.md.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response

from app.core.config import get_data_root
from app.graph_store.store import (
    get_watchlist_entry,
    graph_db_path,
    init_db,
    insert_concept,
    insert_watchlist_entry,
    list_watchlist_entries,
    delete_watchlist_entry,
    set_concept_golden,
    update_watchlist_entry,
)
from app.providers.embeddings import embed_text
from app.providers.factory import build_provider
from app.repositories.config_repository import ConfigError, load_brave_api_key, load_config, load_embeddings_api_key
from app.schemas.watchlist import WatchlistCreateRequest, WatchlistEntry, WatchlistHistory
from app.watchlist.resolver import resolve_watchlist_entry

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_db(data_root):
    db_path = graph_db_path(data_root)
    init_db(db_path)
    return db_path


@router.get("", response_model=WatchlistHistory)
def get_watchlist_endpoint() -> WatchlistHistory:
    data_root = get_data_root()
    db_path = _ensure_db(data_root)
    return WatchlistHistory(entries=list_watchlist_entries(db_path))


@router.post("", response_model=WatchlistEntry)
def post_watchlist_endpoint(payload: WatchlistCreateRequest) -> WatchlistEntry:
    data_root = get_data_root()
    db_path = _ensure_db(data_root)

    entry_id = f"w_{uuid.uuid4().hex[:10]}"
    insert_watchlist_entry(db_path, entry_id, payload.term, _now_iso())

    try:
        config = load_config(data_root)
        embeddings_api_key = load_embeddings_api_key(data_root)
        brave_api_key = load_brave_api_key(data_root)
        llm_provider = build_provider(config, data_root)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved = resolve_watchlist_entry(data_root, entry_id, llm_provider, embeddings_api_key, brave_api_key)
    return WatchlistEntry(**resolved)


@router.patch("/{entry_id}", response_model=WatchlistEntry)
def patch_watchlist_endpoint(entry_id: str, payload: WatchlistCreateRequest) -> WatchlistEntry:
    data_root = get_data_root()
    db_path = _ensure_db(data_root)
    if get_watchlist_entry(db_path, entry_id) is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    # The term changed, so any existing draft/resolution described the OLD
    # term and is now stale — clear it and flip status back to 'pending'
    # (a no-op if it was already pending/rejected) before re-resolving
    # against the new term, uniformly regardless of prior status. This
    # matches the design doc's requirement that editing a resolved entry's
    # term flips it back to pending and clears resolved_concept_id.
    update_watchlist_entry(
        db_path, entry_id, term=payload.term, status="pending", resolved_concept_id=None,
        draft_matched_concept_id=None, draft_definition=None, updated_at=_now_iso(),
    )

    try:
        config = load_config(data_root)
        embeddings_api_key = load_embeddings_api_key(data_root)
        brave_api_key = load_brave_api_key(data_root)
        llm_provider = build_provider(config, data_root)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved = resolve_watchlist_entry(data_root, entry_id, llm_provider, embeddings_api_key, brave_api_key)
    return WatchlistEntry(**resolved)


@router.delete("/{entry_id}", status_code=204)
def delete_watchlist_endpoint(entry_id: str) -> Response:
    data_root = get_data_root()
    db_path = _ensure_db(data_root)
    if get_watchlist_entry(db_path, entry_id) is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    delete_watchlist_entry(db_path, entry_id)
    return Response(status_code=204)


@router.post("/{entry_id}/approve", response_model=WatchlistEntry)
def approve_watchlist_endpoint(entry_id: str) -> WatchlistEntry:
    data_root = get_data_root()
    db_path = _ensure_db(data_root)
    entry = get_watchlist_entry(db_path, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    # draft_matched_concept_id and draft_definition are mutually exclusive
    # (per the resolver's write pattern in app/watchlist/resolver.py): a
    # graph match sets the former and clears the latter, a fresh draft does
    # the reverse. Branch on which one is populated.
    if entry["draft_matched_concept_id"] is not None:
        set_concept_golden(db_path, entry["draft_matched_concept_id"], True)
        resolved_concept_id = entry["draft_matched_concept_id"]
    else:
        try:
            embeddings_api_key = load_embeddings_api_key(data_root)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        embedding = embed_text(embeddings_api_key, entry["draft_definition"])
        concept_id = f"c_{uuid.uuid4().hex[:10]}"
        insert_concept(
            db_path, concept_id, entry["term"], entry["draft_definition"], embedding,
            self_relevant=False, created_at=_now_iso(), golden=True,
        )
        resolved_concept_id = concept_id

    update_watchlist_entry(
        db_path, entry_id, status="resolved", resolved_concept_id=resolved_concept_id, updated_at=_now_iso(),
    )
    return WatchlistEntry(**get_watchlist_entry(db_path, entry_id))


@router.post("/{entry_id}/reject", response_model=WatchlistEntry)
def reject_watchlist_endpoint(entry_id: str) -> WatchlistEntry:
    data_root = get_data_root()
    db_path = _ensure_db(data_root)
    if get_watchlist_entry(db_path, entry_id) is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    update_watchlist_entry(db_path, entry_id, status="rejected", updated_at=_now_iso())
    return WatchlistEntry(**get_watchlist_entry(db_path, entry_id))
