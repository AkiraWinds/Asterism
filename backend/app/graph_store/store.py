"""SQLite-backed concept graph store: concepts, edges, provenance
(concept_highlights), and the medium-confidence dedup review queue. Lives at
{data_root}/.index/graph.db, global across the whole library (unlike
per-source files under library/{id}/). No dedicated graph database is used —
see docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md for
why (Kuzu was archived after its creator's acquisition; SQLite + brute-force
cosine similarity is an accepted prototype fallback at personal-library scale).
"""

import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS concepts (
  id TEXT PRIMARY KEY,
  term TEXT NOT NULL,
  definition TEXT NOT NULL,
  embedding TEXT NOT NULL,
  self_relevant INTEGER NOT NULL DEFAULT 0,
  golden INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_highlights (
  concept_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  highlight_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_sources (
  concept_id TEXT NOT NULL,
  source_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
  id TEXT PRIMARY KEY,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL,
  type TEXT NOT NULL,
  summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
  id TEXT PRIMARY KEY,
  candidate_concept_id TEXT NOT NULL,
  existing_concept_id TEXT NOT NULL,
  llm_judgment TEXT NOT NULL,
  proposed_edge_type TEXT NOT NULL DEFAULT 'related',
  created_at TEXT NOT NULL
);
"""


def graph_db_path(data_root: Path) -> Path:
    return data_root / ".index" / "graph.db"


@contextmanager
def _connect(db_path: Path):
    """Yield a sqlite3 connection and guarantee it is closed on the way out,
    including when execute()/commit() raises (e.g. IntegrityError on a
    duplicate primary key, or a transient OperationalError). graph.db is a
    single shared global file, so a leaked connection here can hold a lock
    that causes "database is locked" errors on every later call in this
    process, unlike per-source files which are only ever touched by one
    request at a time."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        # Migration guard: CREATE TABLE IF NOT EXISTS above is a no-op against a
        # review_queue table that already exists on disk from Phase 6b — it will
        # not add this column. See https://www.sqlite.org/lang_altertable.html —
        # SQLite has no ADD COLUMN IF NOT EXISTS, so check PRAGMA table_info first.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(review_queue)")}
        if "proposed_edge_type" not in cols:
            conn.execute(
                "ALTER TABLE review_queue ADD COLUMN proposed_edge_type TEXT NOT NULL DEFAULT 'related'"
            )
        # Migration guard: concepts table golden column (added for watchlist feature).
        cols = {row[1] for row in conn.execute("PRAGMA table_info(concepts)")}
        if "golden" not in cols:
            conn.execute("ALTER TABLE concepts ADD COLUMN golden INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def insert_concept(
    db_path: Path, concept_id: str, term: str, definition: str, embedding: list[float],
    self_relevant: bool, created_at: str, golden: bool = False,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO concepts (id, term, definition, embedding, self_relevant, golden, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (concept_id, term, definition, json.dumps(embedding), int(self_relevant), int(golden), created_at, created_at),
        )
        conn.commit()


def _row_to_concept_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "term": row["term"],
        "definition": row["definition"],
        "embedding": json.loads(row["embedding"]),
        "self_relevant": row["self_relevant"],
        "golden": bool(row["golden"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_concept(db_path: Path, concept_id: str) -> dict | None:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM concepts WHERE id = ?", (concept_id,)).fetchone()
        return _row_to_concept_dict(row) if row else None


def list_concepts(db_path: Path) -> list[dict]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM concepts").fetchall()
        return [_row_to_concept_dict(r) for r in rows]


def delete_concept(db_path: Path, concept_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))
        conn.commit()


def set_concept_golden(db_path: Path, concept_id: str, golden: bool) -> None:
    """Flip a concept's golden flag, e.g. when a watchlist entry resolves to
    an existing concept rather than minting a new one (see app/watchlist/resolver.py)."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE concepts SET golden = ? WHERE id = ?", (int(golden), concept_id))
        conn.commit()


def link_concept_highlight(db_path: Path, concept_id: str, source_id: str, highlight_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO concept_highlights (concept_id, source_id, highlight_id) VALUES (?, ?, ?)",
            (concept_id, source_id, highlight_id),
        )
        conn.commit()


def link_concept_source(db_path: Path, concept_id: str, source_id: str) -> None:
    """Provenance for a concept that came from a source's auto-extracted
    digest concepts, with no highlight involved — the Tier-1 (Phase 6b-2)
    counterpart to link_concept_highlight."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO concept_sources (concept_id, source_id) VALUES (?, ?)",
            (concept_id, source_id),
        )
        conn.commit()


def delete_concept_highlights_for_highlight(db_path: Path, highlight_id: str) -> None:
    """Clear one highlight's provenance links, e.g. before re-running extraction
    on a PATCH note edit. Does not delete the concept rows themselves — a
    concept may still be linked from other highlights."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM concept_highlights WHERE highlight_id = ?", (highlight_id,))
        conn.commit()


def delete_concept_sources_for_source(db_path: Path, source_id: str) -> None:
    """Clear one source's Tier-1 provenance links before re-running
    process_source_concepts on a re-analyze, e.g. so a retry doesn't
    re-insert duplicate (concept_id, source_id) rows. Does not delete the
    concept rows themselves — a concept may still be linked from other
    sources or highlights."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM concept_sources WHERE source_id = ?", (source_id,))
        conn.commit()


def repoint_concept_highlights(db_path: Path, old_concept_id: str, new_concept_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE concept_highlights SET concept_id = ? WHERE concept_id = ?",
            (new_concept_id, old_concept_id),
        )
        conn.commit()


def repoint_edges(db_path: Path, old_concept_id: str, new_concept_id: str) -> None:
    """Retarget any edge endpoints pointing at old_concept_id, e.g. before
    deleting a concept merged into another — otherwise the deleted concept's
    id survives as a dangling from_id/to_id that GET /graph would still
    return, crashing the client-side force-graph renderer."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE edges SET from_id = ? WHERE from_id = ?",
            (new_concept_id, old_concept_id),
        )
        conn.execute(
            "UPDATE edges SET to_id = ? WHERE to_id = ?",
            (new_concept_id, old_concept_id),
        )
        conn.commit()


def insert_edge(db_path: Path, edge_id: str, from_id: str, to_id: str, edge_type: str, summary: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO edges (id, from_id, to_id, type, summary) VALUES (?, ?, ?, ?, ?)",
            (edge_id, from_id, to_id, edge_type, summary),
        )
        conn.commit()


def list_edges(db_path: Path) -> list[dict]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM edges").fetchall()
        return [dict(r) for r in rows]


def insert_review_queue_entry(
    db_path: Path, entry_id: str, candidate_concept_id: str, existing_concept_id: str,
    llm_judgment: str, created_at: str, proposed_edge_type: str = "related",
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO review_queue (id, candidate_concept_id, existing_concept_id, llm_judgment, "
            "proposed_edge_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (entry_id, candidate_concept_id, existing_concept_id, llm_judgment, proposed_edge_type, created_at),
        )
        conn.commit()


def list_review_queue(db_path: Path) -> list[dict]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM review_queue").fetchall()
        return [dict(r) for r in rows]


def get_review_queue_entry(db_path: Path, entry_id: str) -> dict | None:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM review_queue WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None


def delete_review_queue_entry(db_path: Path, entry_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM review_queue WHERE id = ?", (entry_id,))
        conn.commit()


# Small tiebreaker bonus for golden concepts in ranking. Helps near-duplicate detection
# prefer user-approved matches without letting an unrelated golden concept outrank a
# genuinely close non-golden match. See design doc's Resolution chain for rationale.
_GOLDEN_BONUS = 0.05


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def nearest_neighbors(db_path: Path, embedding: list[float], top_k: int = 3) -> list[tuple[dict, float]]:
    """Brute-force cosine similarity over every stored concept. Fine at
    personal-library scale; revisit with a real vector index only if this
    becomes a measured bottleneck (see design doc's Out of Scope). Golden
    concepts (user-approved via the watchlist) get a small fixed bonus so
    they win ties against near-duplicate non-golden matches, without letting
    a barely-related golden concept outrank a genuinely close match."""
    candidates = list_concepts(db_path)
    # Add small bonus to golden concepts to break ties in deduplication without
    # letting unrelated golden concepts outrank close non-golden matches.
    scored = [
        (c, _cosine_similarity(embedding, c["embedding"]) + (_GOLDEN_BONUS if c["golden"] else 0.0))
        for c in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
