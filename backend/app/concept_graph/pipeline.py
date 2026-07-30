"""Orchestrates the synchronous per-highlight pipeline: extract concepts,
embed each, find nearest-neighbor candidates, judge dedup, and apply/queue
the result. Triggered inline by POST /sources/{id}/highlights — see
docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.concept_graph.prompts import (
    build_dedup_prompt,
    build_extraction_prompt,
    parse_dedup_response,
    parse_extraction_response,
)
from app.graph_store.store import (
    get_concept,
    graph_db_path,
    init_db,
    insert_concept,
    insert_edge,
    insert_review_queue_entry,
    link_concept_highlight,
    nearest_neighbors,
)
from app.providers.base import Provider
from app.providers.embeddings import embed_text
from app.schemas.graph import ConceptNode, Edge, HighlightProcessResult, ReviewQueueEntry
from app.schemas.highlight import Highlight

# The extraction step's "relationship" field uses "related_to"/"none" to describe
# what a note signals; edge storage only distinguishes related/contradicts/extends,
# so both of those collapse to "related" when an edge actually gets created.
_RELATIONSHIP_TO_EDGE_TYPE = {
    "contradicts": "contradicts",
    "extends": "extends",
    "related_to": "related",
    "none": "related",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def process_highlight(
    data_root: Path,
    source_id: str,
    highlight: Highlight,
    llm_provider: Provider,
    embeddings_api_key: str,
) -> HighlightProcessResult:
    db_path = graph_db_path(data_root)
    # CREATE TABLE IF NOT EXISTS makes this idempotent and cheap — safe to call
    # on every invocation rather than requiring callers to initialize the store
    # separately (there's no app-startup hook that does this once).
    init_db(db_path)

    try:
        raw_extraction = llm_provider.complete(build_extraction_prompt(highlight.source_quote, highlight.note))
        extracted = parse_extraction_response(raw_extraction)
    except ValueError as exc:
        return HighlightProcessResult(highlight=highlight, extraction_error=str(exc))

    created_concepts: list[ConceptNode] = []
    created_edges: list[Edge] = []
    queued: list[ReviewQueueEntry] = []

    for item in extracted:
        embedding = embed_text(embeddings_api_key, item["definition"])
        neighbors = nearest_neighbors(db_path, embedding, top_k=3)

        if not neighbors:
            concept_id = f"c_{uuid.uuid4().hex[:10]}"
            now = _now_iso()
            insert_concept(db_path, concept_id, item["term"], item["definition"], embedding, item["self_relevant"], now)
            link_concept_highlight(db_path, concept_id, source_id, highlight.id)
            created_concepts.append(ConceptNode(
                id=concept_id, term=item["term"], definition=item["definition"], self_relevant=item["self_relevant"]
            ))
            continue

        neighbor_payload = [{"id": c["id"], "term": c["term"], "definition": c["definition"]} for c, _ in neighbors]
        raw_dedup = llm_provider.complete(
            build_dedup_prompt(item["term"], item["definition"], highlight.note, neighbor_payload)
        )
        judgments = parse_dedup_response(raw_dedup)

        best = judgments[0]
        existing = get_concept(db_path, best["existing_concept_id"])

        if best["judgment"] == "same":
            link_concept_highlight(db_path, existing["id"], source_id, highlight.id)
            continue

        if best["judgment"] == "new":
            concept_id = f"c_{uuid.uuid4().hex[:10]}"
            now = _now_iso()
            insert_concept(db_path, concept_id, item["term"], item["definition"], embedding, item["self_relevant"], now)
            link_concept_highlight(db_path, concept_id, source_id, highlight.id)
            created_concepts.append(ConceptNode(
                id=concept_id, term=item["term"], definition=item["definition"], self_relevant=item["self_relevant"]
            ))
            continue

        # judgment == "related_distinct"
        concept_id = f"c_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        insert_concept(db_path, concept_id, item["term"], item["definition"], embedding, item["self_relevant"], now)
        link_concept_highlight(db_path, concept_id, source_id, highlight.id)
        created_concepts.append(ConceptNode(
            id=concept_id, term=item["term"], definition=item["definition"], self_relevant=item["self_relevant"]
        ))

        if best["confidence"] == "high":
            edge_id = f"e_{uuid.uuid4().hex[:10]}"
            edge_type = _RELATIONSHIP_TO_EDGE_TYPE[item["relationship"]]
            insert_edge(db_path, edge_id, concept_id, existing["id"], edge_type, best["summary"])
            created_edges.append(Edge(id=edge_id, from_id=concept_id, to_id=existing["id"], type=edge_type, summary=best["summary"]))
        else:
            entry_id = f"rq_{uuid.uuid4().hex[:10]}"
            insert_review_queue_entry(db_path, entry_id, concept_id, existing["id"], best["summary"], now)
            queued.append(ReviewQueueEntry(
                id=entry_id, candidate_concept_id=concept_id, existing_concept_id=existing["id"],
                llm_judgment=best["summary"], created_at=now,
            ))

    return HighlightProcessResult(highlight=highlight, concepts=created_concepts, edges=created_edges, queued=queued)
