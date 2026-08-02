"""SQLite-backed store for Radar (proactive content discovery feed):
feed_sources (curated RSS sources), boost_topics (manual interest boosts),
and radar_items (ranked recommendations awaiting user action). Lives at
{data_root}/.index/radar.db — a separate file from graph.db since Radar's
lifecycle (item expiry, per-source fetch health) is unrelated to
concept-graph state. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_fetched_at TEXT NULL,
  last_fetch_status TEXT NULL,
  last_fetch_error TEXT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boost_topics (
  id TEXT PRIMARY KEY,
  term TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS radar_items (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  published_at TEXT NULL,
  relevance_score REAL NOT NULL,
  quality_score REAL NOT NULL,
  reasoning TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  added_source_id TEXT NULL,
  created_at TEXT NOT NULL
);
"""

# Seeded on first init_db only (table starts empty). Editable/removable via
# the CRUD API immediately after — not a hardcoded runtime list, just a
# starting point. Anthropic has no official RSS feed as of this writing, so
# it's deliberately left off rather than seeding a fragile unofficial mirror.
DEFAULT_FEED_SOURCES = [
    ("OpenAI Blog", "https://openai.com/news/rss.xml"),
    ("LangChain Blog", "https://www.langchain.com/blog/rss.xml"),
    ("OpenAI Cookbook", "https://developers.openai.com/rss.xml"),
]


def radar_db_path(data_root: Path) -> Path:
    return data_root / ".index" / "radar.db"


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _row_to_feed_source(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    return d


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM feed_sources").fetchone()[0]
        if count == 0:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            for i, (name, url) in enumerate(DEFAULT_FEED_SOURCES):
                conn.execute(
                    "INSERT INTO feed_sources (id, name, url, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
                    (f"seed_{i}", name, url, now),
                )
        conn.commit()


def insert_feed_source(db_path: Path, source_id: str, name: str, url: str, created_at: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO feed_sources (id, name, url, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
            (source_id, name, url, created_at),
        )
        conn.commit()


def list_feed_sources(db_path: Path) -> list[dict]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM feed_sources").fetchall()
        return [_row_to_feed_source(r) for r in rows]


def get_feed_source(db_path: Path, source_id: str) -> dict | None:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM feed_sources WHERE id = ?", (source_id,)).fetchone()
        return _row_to_feed_source(row) if row else None


def update_feed_source(
    db_path: Path, source_id: str, *, name: str | None = None, url: str | None = None, enabled: bool | None = None
) -> None:
    current = get_feed_source(db_path, source_id)
    if current is None:
        return
    new_name = name if name is not None else current["name"]
    new_url = url if url is not None else current["url"]
    new_enabled = int(enabled) if enabled is not None else int(current["enabled"])
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE feed_sources SET name = ?, url = ?, enabled = ? WHERE id = ?",
            (new_name, new_url, new_enabled, source_id),
        )
        conn.commit()


def update_feed_source_fetch_status(db_path: Path, source_id: str, *, status: str, error: str | None, fetched_at: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE feed_sources SET last_fetch_status = ?, last_fetch_error = ?, last_fetched_at = ? WHERE id = ?",
            (status, error, fetched_at, source_id),
        )
        conn.commit()


def delete_feed_source(db_path: Path, source_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM feed_sources WHERE id = ?", (source_id,))
        conn.commit()


def insert_boost_topic(db_path: Path, topic_id: str, term: str, created_at: str) -> None:
    """Insert a manual interest boost topic."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO boost_topics (id, term, created_at) VALUES (?, ?, ?)", (topic_id, term, created_at)
        )
        conn.commit()


def list_boost_topics(db_path: Path) -> list[dict]:
    """List all boost topics."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM boost_topics").fetchall()
        return [dict(r) for r in rows]


def get_boost_topic(db_path: Path, topic_id: str) -> dict | None:
    """Get a single boost topic by ID."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM boost_topics WHERE id = ?", (topic_id,)).fetchone()
        return dict(row) if row else None


def delete_boost_topic(db_path: Path, topic_id: str) -> None:
    """Delete a boost topic by ID."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM boost_topics WHERE id = ?", (topic_id,))
        conn.commit()


def insert_radar_item(
    db_path: Path, *, item_id: str, source_id: str, url: str, title: str, summary: str,
    published_at: str | None, relevance_score: float, quality_score: float, reasoning: str, created_at: str,
) -> bool:
    """Insert a radar item. Returns False (no-op) if url already exists — UNIQUE constraint is the dedup-across-runs mechanism."""
    try:
        with _connect(db_path) as conn:
            conn.execute(
                "INSERT INTO radar_items "
                "(id, source_id, url, title, summary, published_at, relevance_score, quality_score, reasoning, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)",
                (item_id, source_id, url, title, summary, published_at, relevance_score, quality_score, reasoning, created_at),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        # URL already exists; dedup by returning False without inserting.
        return False


def list_new_radar_items(db_path: Path, cutoff_iso: str) -> list[dict]:
    """List new radar items created at or after cutoff_iso, ordered by relevance_score descending."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM radar_items WHERE status = 'new' AND created_at >= ? ORDER BY relevance_score DESC",
            (cutoff_iso,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_radar_item(db_path: Path, item_id: str) -> dict | None:
    """Get a radar item by ID."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM radar_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


def update_radar_item_status(db_path: Path, item_id: str, *, status: str, added_source_id: str | None = None) -> None:
    """Update a radar item's status and optionally the source it was added to."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE radar_items SET status = ?, added_source_id = ? WHERE id = ?",
            (status, added_source_id, item_id),
        )
        conn.commit()


def list_all_radar_item_urls(db_path: Path) -> set[str]:
    """Get all URLs in the radar_items table (used for dedup checking)."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT url FROM radar_items").fetchall()
        return {r[0] for r in rows}
