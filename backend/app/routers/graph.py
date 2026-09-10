# backend/app/routers/graph.py
"""API routes for the Phase 6b concept graph: read-only graph view and the
medium-confidence dedup review queue. See
docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.core.config import get_data_root
from app.graph_store.store import (
    delete_concept,
    delete_review_queue_entry,
    get_review_queue_entry,
    graph_db_path,
    init_db,
    insert_edge,
    list_review_queue,
    repoint_concept_highlights,
    repoint_edges,
)
from app.graph_store.view import build_graph_response
from app.schemas.graph import GraphResponse, ReviewQueueEntry, ReviewQueueResolveRequest

router = APIRouter(prefix="/graph", tags=["graph"])


def _ensure_db():
    data_root = get_data_root()
    db_path = graph_db_path(data_root)
    if not db_path.exists():
        init_db(db_path)
    return db_path


@router.get("", response_model=GraphResponse)
def get_graph_endpoint() -> GraphResponse:
    data_root = get_data_root()
    db_path = _ensure_db()
    return build_graph_response(data_root, db_path)


@router.get("/review-queue", response_model=list[ReviewQueueEntry])
def list_review_queue_endpoint() -> list[ReviewQueueEntry]:
    db_path = _ensure_db()
    return [
        ReviewQueueEntry(
            id=e["id"], candidate_concept_id=e["candidate_concept_id"],
            existing_concept_id=e["existing_concept_id"], llm_judgment=e["llm_judgment"],
            proposed_edge_type=e["proposed_edge_type"], created_at=e["created_at"],
        )
        for e in list_review_queue(db_path)
    ]


@router.post("/review-queue/{entry_id}/resolve")
def resolve_review_queue_endpoint(entry_id: str, payload: ReviewQueueResolveRequest):
    db_path = _ensure_db()
    entry = get_review_queue_entry(db_path, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Review queue entry not found")

    if payload.action == "merge":
        repoint_concept_highlights(db_path, entry["candidate_concept_id"], entry["existing_concept_id"])
        repoint_edges(db_path, entry["candidate_concept_id"], entry["existing_concept_id"])
        delete_concept(db_path, entry["candidate_concept_id"])
    else:
        edge_id = f"e_{uuid.uuid4().hex[:10]}"
        insert_edge(
            db_path, edge_id, entry["candidate_concept_id"], entry["existing_concept_id"],
            entry["proposed_edge_type"], entry["llm_judgment"],
        )

    delete_review_queue_entry(db_path, entry_id)
    return {"status": "resolved"}
