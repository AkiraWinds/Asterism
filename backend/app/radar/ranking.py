"""Dedup and coarse relevance filtering for Radar. The coarse filter embeds
each candidate item's title+summary and scores it against the user's
concept graph (plus manual boost topics) via cosine similarity — cheap
enough to run over every RSS item, unlike the LLM judgment pass (app.radar.
judge), which only runs on the resulting shortlist. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import math
from pathlib import Path

from app.graph_store.store import nearest_neighbors
from app.providers.embeddings import embed_text


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
    graph_db_path: Path, embeddings_api_key: str, items: list[dict], boost_terms: list[str], top_n: int = 20
) -> list[dict]:
    """Scores each item by the best of: its similarity to the nearest
    concept-graph concept, or its similarity to any boost topic. Returns the
    top_n items sorted by that score descending, each with a _coarse_score
    field attached."""
    boost_embeddings = [embed_text(embeddings_api_key, term) for term in boost_terms]

    scored = []
    for item in items:
        text = f"{item['title']}\n{item.get('summary', '')}"
        embedding = embed_text(embeddings_api_key, text)

        best = 0.0
        neighbors = nearest_neighbors(graph_db_path, embedding, top_k=1)
        if neighbors:
            _, true_similarity, _ = neighbors[0]
            best = max(best, true_similarity)
        for boost_embedding in boost_embeddings:
            best = max(best, _cosine_similarity(embedding, boost_embedding))

        scored.append({**item, "_coarse_score": best})

    scored.sort(key=lambda i: i["_coarse_score"], reverse=True)
    return scored[:top_n]
