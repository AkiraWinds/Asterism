"""Orchestrates the synchronous per-highlight (and, per Phase 6b-2, per-source)
pipeline: for a batch of {term, definition, self_relevant} items, embed each,
find nearest-neighbor candidates, judge dedup + relationship, and apply/queue
the result. `process_highlight` is triggered inline by
POST /sources/{id}/highlights; `process_source_concepts` (added in Phase 6b-2)
is triggered inline by POST /sources/{id}/analyze. Both share the
embed→dedup→apply loop via `_dedupe_and_insert`. See
docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b2-design.md.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

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
    nearest_neighbors,
)
from app.providers.base import Provider, ProviderError
from app.providers.embeddings import embed_text
from app.schemas.graph import ConceptNode, Edge, HighlightProcessResult, ReviewQueueEntry
from app.schemas.highlight import Highlight

logger = logging.getLogger(__name__)

# The dedup step's "relationship" field describes what the candidate's
# relationship to a matched neighbor is; edge storage only distinguishes
# related/contradicts/extends, so an unrecognized or "related_to"/"none"
# value collapses to "related" when an edge actually gets created.
_RELATIONSHIP_TO_EDGE_TYPE = {
    "contradicts": "contradicts",
    "extends": "extends",
    "related_to": "related",
    "none": "related",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _select_judgment(judgments: list[dict]) -> dict:
    """Pick which per-neighbor dedup judgment to act on.

    The dedup prompt returns one judgment per neighbor considered, but the
    pipeline only acts on a single one. A "same" judgment anywhere in the list
    represents a real duplicate and must never be discarded just because an
    earlier neighbor in the list happened to be judged "new"/"related_distinct"
    first — that would silently create a duplicate concept. Preference order:
    1. any "same" judgment (a real dup takes priority over everything else)
    2. "related_distinct" with the highest confidence (high over medium)
    3. any "new" judgment
    4. otherwise, the first entry (defensive fallback for unexpected shapes)
    """
    if not judgments:
        raise ValueError("dedup response contained no judgments")

    for j in judgments:
        if j.get("judgment") == "same":
            return j

    related = [j for j in judgments if j.get("judgment") == "related_distinct"]
    if related:
        return max(related, key=lambda j: 1 if j.get("confidence") == "high" else 0)

    for j in judgments:
        if j.get("judgment") == "new":
            return j

    return judgments[0]


def _dedupe_and_insert(
    db_path: Path,
    items: list[dict],
    note: str | None,
    link_fn: Callable[[str], None],
    llm_provider: Provider,
    embeddings_api_key: str,
    log_context: str,
) -> tuple[list[ConceptNode], list[Edge], list[ReviewQueueEntry], str | None]:
    """Runs embed -> nearest-neighbor -> dedup-judge -> apply/queue for each
    item. Returns (concepts, edges, queued, error) — error is None on full
    success. On a mid-loop failure, whatever was already committed for
    earlier items in this call is still returned alongside the error string
    (no rollback), matching this pipeline's existing partial-commit-on-error
    behavior."""
    created_concepts: list[ConceptNode] = []
    created_edges: list[Edge] = []
    queued: list[ReviewQueueEntry] = []

    def _create_concept(item: dict, embedding: list[float]) -> ConceptNode:
        concept_id = f"c_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        insert_concept(db_path, concept_id, item["term"], item["definition"], embedding, item["self_relevant"], now)
        link_fn(concept_id)
        return ConceptNode(
            id=concept_id, term=item["term"], definition=item["definition"], self_relevant=item["self_relevant"]
        )

    try:
        for item in items:
            embedding = embed_text(embeddings_api_key, item["definition"])
            neighbors = nearest_neighbors(db_path, embedding, top_k=3)

            if not neighbors:
                created_concepts.append(_create_concept(item, embedding))
                continue

            neighbor_payload = [{"id": c["id"], "term": c["term"], "definition": c["definition"]} for c, _ in neighbors]
            raw_dedup = llm_provider.complete(build_dedup_prompt(item["term"], item["definition"], note, neighbor_payload))
            judgments = parse_dedup_response(raw_dedup)

            best = _select_judgment(judgments)
            existing = get_concept(db_path, best["existing_concept_id"])
            if existing is None:
                # The dedup prompt only ever hands the model IDs drawn from `neighbors`,
                # so an existing_concept_id that doesn't resolve is a hallucinated/invalid
                # response, not a legitimate signal — treat it the same as malformed JSON
                # rather than silently falling through to "new" and masking the failure.
                raise ValueError(
                    f"dedup response named unknown existing_concept_id: {best['existing_concept_id']!r}"
                )

            if best["judgment"] == "same":
                link_fn(existing["id"])
                continue

            if best["judgment"] == "new":
                created_concepts.append(_create_concept(item, embedding))
                continue

            # judgment == "related_distinct"
            concept_node = _create_concept(item, embedding)
            created_concepts.append(concept_node)

            edge_type = _RELATIONSHIP_TO_EDGE_TYPE.get(best["relationship"], "related")
            if best["confidence"] == "high" and edge_type != "contradicts":
                edge_id = f"e_{uuid.uuid4().hex[:10]}"
                insert_edge(db_path, edge_id, concept_node.id, existing["id"], edge_type, best["summary"])
                created_edges.append(Edge(id=edge_id, from_id=concept_node.id, to_id=existing["id"], type=edge_type, summary=best["summary"]))
            else:
                entry_id = f"rq_{uuid.uuid4().hex[:10]}"
                now = _now_iso()
                insert_review_queue_entry(
                    db_path, entry_id, concept_node.id, existing["id"], best["summary"], now,
                    proposed_edge_type=edge_type,
                )
                queued.append(ReviewQueueEntry(
                    id=entry_id, candidate_concept_id=concept_node.id, existing_concept_id=existing["id"],
                    llm_judgment=best["summary"], proposed_edge_type=edge_type, created_at=now,
                ))
    except (ValueError, ProviderError) as exc:
        logger.exception("Concept graph dedup pipeline failed (%s)", log_context)
        return created_concepts, created_edges, queued, str(exc)

    return created_concepts, created_edges, queued, None


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
    except (ValueError, ProviderError) as exc:
        return HighlightProcessResult(highlight=highlight, extraction_error=str(exc))

    from app.graph_store.store import link_concept_highlight

    concepts, edges, queued, error = _dedupe_and_insert(
        db_path, extracted, highlight.note,
        link_fn=lambda concept_id: link_concept_highlight(db_path, concept_id, source_id, highlight.id),
        llm_provider=llm_provider, embeddings_api_key=embeddings_api_key,
        log_context=f"highlight id={highlight.id} source_id={source_id}",
    )
    if error is not None:
        return HighlightProcessResult(highlight=highlight, concepts=concepts, edges=edges, queued=queued, extraction_error=error)

    return HighlightProcessResult(highlight=highlight, concepts=concepts, edges=edges, queued=queued)
