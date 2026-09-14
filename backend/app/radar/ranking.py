"""Dedup and coarse relevance filtering for Radar. The coarse filter embeds
each candidate item's title+summary and scores it against the user's
concept graph (plus manual boost topics) via cosine similarity — cheap
enough to run over every RSS item, unlike the LLM judgment pass (app.radar.
judge), which only runs on the resulting shortlist. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import math
from datetime import datetime, timezone
from pathlib import Path

from app.graph_store.store import nearest_neighbors
from app.providers.embeddings import embed_text
from app.repositories.config_repository import DEFAULT_EMBEDDINGS_MODEL

# Radar runs roughly daily, so a 3-day half-life means a brand-new post
# scores meaningfully higher than an equally-similar item pulled from a
# source's entire historical backlog (previously they competed purely on
# embedding similarity — see todo.md's 2026-09-11 Radar entry). The floor
# keeps this a deprioritization, not an elimination: a much older item that's
# far more relevant can still outrank a barely-relevant new one.
RADAR_RECENCY_HALF_LIFE_DAYS = 3.0
RADAR_RECENCY_FLOOR = 0.2


def _recency_weight(published_at: str | None, *, now: datetime | None = None) -> float:
    """Exponential decay by age in days, floored at RADAR_RECENCY_FLOOR.
    Returns 1.0 (no penalty) when there's no date to score against — some
    feeds omit published_at entirely, and an unknown age shouldn't be
    treated as an old one."""
    if not published_at:
        return 1.0
    try:
        published = datetime.fromisoformat(published_at)
    except ValueError:
        return 1.0
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    age_days = max(((now or datetime.now(timezone.utc)) - published).total_seconds() / 86400.0, 0.0)
    return max(0.5 ** (age_days / RADAR_RECENCY_HALF_LIFE_DAYS), RADAR_RECENCY_FLOOR)


def filter_new_items(items: list[dict], seen_urls: set[str]) -> list[dict]:
    return [item for item in items if item["url"] not in seen_urls]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def coarse_filter(
    graph_db_path: Path, embeddings_api_key: str, items: list[dict], boost_terms: list[str], top_n: int = 20,
    embeddings_model: str = DEFAULT_EMBEDDINGS_MODEL, return_rejected: bool = False,
) -> list[dict] | tuple[list[dict], list[dict]]:
    """Scores each item by the best of: its similarity to the nearest
    concept-graph concept, or its similarity to any boost topic, multiplied
    by a recency weight (see _recency_weight) so a source's older backlog
    doesn't compete evenly against genuinely new posts. Returns the top_n
    items sorted by that score descending, each with a _coarse_score field
    attached.

    `return_rejected` defaults to False so every existing caller keeps its
    original contract (a plain list) untouched. Pass True to additionally get
    back every item that scored below the top_n cutoff, as (shortlist,
    rejected) — app.radar.pipeline uses this to persist those losers instead
    of silently discarding them, so they're not re-embedded (this function's
    only real cost) on every future run. See docs/learning-notes.md's
    2026-09-11 "Function / API contract" entry for why this was added as a
    new parameter rather than changing the return shape outright."""
    boost_embeddings = [embed_text(embeddings_api_key, term, model=embeddings_model) for term in boost_terms]

    scored = []
    for item in items:
        text = f"{item['title']}\n{item.get('summary', '')}"
        embedding = embed_text(embeddings_api_key, text, model=embeddings_model)

        best = 0.0
        neighbors = nearest_neighbors(graph_db_path, embedding, top_k=1)
        if neighbors:
            _, true_similarity, _ = neighbors[0]
            best = max(best, true_similarity)
        for boost_embedding in boost_embeddings:
            best = max(best, _cosine_similarity(embedding, boost_embedding))

        weighted = best * _recency_weight(item.get("published_at"))
        scored.append({**item, "_coarse_score": weighted})

    scored.sort(key=lambda i: i["_coarse_score"], reverse=True)
    if return_rejected:
        return scored[:top_n], scored[top_n:]
    return scored[:top_n]
