"""Read-only helpers over graph.db for the wiki compile layer. Never inserts,
updates, or deletes — concept/edge identity stays entirely owned by
app.graph_store.store and app.concept_graph.pipeline. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md.
"""

import sqlite3
from pathlib import Path

from app.graph_store.store import list_edges
from app.repositories.source_repository import get_source, read_highlights


def get_concept_provenance(db_path: Path, concept_id: str) -> list[dict]:
    """Union of concept_highlights (highlight-derived, Phase 6b) and
    concept_sources (digest-derived, Phase 6b-2) provenance rows for one
    concept. init_db() always creates both tables unconditionally, so no
    existence check is needed here. Each row:
    {"source_id": str, "highlight_id": str | None}.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source_id, highlight_id FROM concept_highlights WHERE concept_id = ?",
            (concept_id,),
        ).fetchall()
        result = [{"source_id": r["source_id"], "highlight_id": r["highlight_id"]} for r in rows]
        source_rows = conn.execute(
            "SELECT source_id FROM concept_sources WHERE concept_id = ?",
            (concept_id,),
        ).fetchall()
        result.extend({"source_id": r["source_id"], "highlight_id": None} for r in source_rows)
        return result
    finally:
        conn.close()


def get_edges_for_concept(db_path: Path, concept_id: str) -> list[dict]:
    """Brute-force filter over all edges — fine at personal-library scale,
    matching the same tradeoff app.graph_store.store.nearest_neighbors makes."""
    return [e for e in list_edges(db_path) if e["from_id"] == concept_id or e["to_id"] == concept_id]


def resolve_citations(data_root: Path, provenance: list[dict]) -> list[dict]:
    """Human-readable citation for each provenance row: {"source_id", "label",
    "quote"}. quote is the highlight's exact source_quote when the row came
    from a highlight; None for digest-derived (Phase 6b-2) rows, which have
    no single quote. label prefers the highlight's denormalized source_title,
    then the source's own title, then the raw source_id."""
    highlights_cache: dict[str, dict] = {}
    citations = []
    for row in provenance:
        source_id = row["source_id"]
        highlight_id = row["highlight_id"]
        if highlight_id:
            if source_id not in highlights_cache:
                history = read_highlights(data_root, source_id)
                highlights_cache[source_id] = {h.id: h for h in history.highlights}
            highlight = highlights_cache[source_id].get(highlight_id)
            if highlight:
                citations.append({"source_id": source_id, "label": highlight.source_title, "quote": highlight.source_quote})
                continue
        record = get_source(data_root, source_id)
        label = record.title if record else source_id
        citations.append({"source_id": source_id, "label": label, "quote": None})
    return citations
