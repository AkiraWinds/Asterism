"""Resolution chain for a user-declared watchlist term (Phase 6, decision 8):
check the existing concept graph first, fall back to web search, fall back to
the LLM's own reasoning. Writes a draft (or a matched-concept pointer) onto
the watchlist entry for the user to approve/reject via
app/routers/watchlist.py — never creates or mutates a concept directly (that
only happens on approval). See
docs/superpowers/specs/2026-08-01-entity-extraction-reference-lookup-design.md.
"""

from datetime import datetime, timezone
from pathlib import Path

from app.graph_store.store import (
    get_watchlist_entry,
    graph_db_path,
    init_db,
    nearest_neighbors,
    update_watchlist_entry,
)
from app.providers.base import Provider, ProviderError
from app.providers.embeddings import embed_text
from app.search.brave import search_web

# True cosine similarity (nearest_neighbors' true_similarity, NOT its
# golden-boosted ranking score — see graph_store/store.py's nearest_neighbors)
# above which a watchlist term is treated as already covered by an existing
# concept, rather than needing a fresh draft. Comparing against the boosted
# score here would let a golden concept's +0.05 tie-breaker bonus (meant only
# to break ties in ranking) push a term across this absolute cutoff on true
# similarity alone — e.g. a golden concept at true similarity 0.81 must NOT
# count as a match just because boosting puts it at 0.86. Deliberately a
# fixed threshold rather than another LLM-judged
# dedup call — proportionate to this being a low-frequency, user-reviewed
# action (you approve/reject the outcome either way), not the
# every-highlight extraction hot path that justifies the fuller LLM-judgment
# dedup flow in concept_graph/pipeline.py.
_MATCH_THRESHOLD = 0.85


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_watchlist_entry(
    data_root: Path, entry_id: str, llm_provider: Provider, embeddings_api_key: str, brave_api_key: str | None,
) -> dict:
    db_path = graph_db_path(data_root)
    init_db(db_path)
    entry = get_watchlist_entry(db_path, entry_id)
    if entry is None:
        raise ValueError(f"No watchlist entry with id {entry_id!r}")

    term_embedding = embed_text(embeddings_api_key, entry["term"])
    neighbors = nearest_neighbors(db_path, term_embedding, top_k=1)

    # Graph match: nearest neighbor's TRUE similarity clears the threshold,
    # so treat the term as already covered by an existing concept rather
    # than drafting a new one.
    if neighbors and neighbors[0][1] >= _MATCH_THRESHOLD:
        matched_concept, _true_similarity, _boosted_score = neighbors[0]
        update_watchlist_entry(
            db_path, entry_id, draft_matched_concept_id=matched_concept["id"], draft_definition=None,
            updated_at=_now_iso(),
        )
        return get_watchlist_entry(db_path, entry_id)

    draft_definition = None
    if brave_api_key is not None:
        try:
            results = search_web(brave_api_key, entry["term"])
        except ProviderError:
            # Web search unavailable (auth failure, rate limit, network error) —
            # fall through to LLM reasoning rather than surfacing a raw error.
            results = []
        top_description = results[0].get("description", "") if results else ""
        if top_description:
            draft_definition = f"{top_description} (source: {results[0]['url']})"

    if draft_definition is None:
        draft_definition = llm_provider.complete(
            f"Give a concise 1-2 sentence definition of the term: {entry['term']}"
        )

    update_watchlist_entry(
        db_path, entry_id, draft_matched_concept_id=None, draft_definition=draft_definition, updated_at=_now_iso(),
    )
    return get_watchlist_entry(db_path, entry_id)
