"""Read-only helpers over graph.db for the wiki compile layer. Never inserts,
updates, or deletes — concept/edge identity stays entirely owned by
app.graph_store.store and app.concept_graph.pipeline. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md.
"""

import sqlite3
from pathlib import Path

from app.graph_store.store import list_edges


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def get_concept_provenance(db_path: Path, concept_id: str) -> list[dict]:
    """Union of concept_highlights (highlight-derived, Phase 6b) and
    concept_sources (digest-derived, Phase 6b-2 — read only if the table
    exists, since 6b-2 may not be built on this graph.db yet) provenance rows
    for one concept. Each row: {"source_id": str, "highlight_id": str | None}.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source_id, highlight_id FROM concept_highlights WHERE concept_id = ?",
            (concept_id,),
        ).fetchall()
        result = [{"source_id": r["source_id"], "highlight_id": r["highlight_id"]} for r in rows]
        if _table_exists(conn, "concept_sources"):
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
