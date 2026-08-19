"""Read-only helpers over graph.db for the wiki compile layer. Never inserts,
updates, or deletes — concept/edge identity stays entirely owned by
app.graph_store.store and app.concept_graph.pipeline. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md.
"""

import json
import logging
import sqlite3
from pathlib import Path

from app.graph_store.store import list_edges
from app.repositories.source_repository import get_source, read_highlights
from app.wiki.render import extract_body, parse_wiki_page_frontmatter

logger = logging.getLogger(__name__)


def scan_wiki_pages(wiki_dir: Path) -> dict[str, dict]:
    """concept_id -> {"slug", "frontmatter"} for every existing wiki *overview*
    page (skips aspect sub-pages, identified by an `aspect_of` frontmatter key
    — see docs/superpowers/specs/2026-08-01-wiki-many-to-many-redesign-design.md
    — so that a concept with aspect pages still resolves unambiguously to its
    one overview page). Shared by the wiki compile pipeline (which needs the
    full existing-page map to decide new/unchanged/reused-slug per compile
    run) and the read-only wiki-page API (which looks up a single concept_id
    at request time — a per-request full scan is fine at this repo's
    personal-library scale, matching the precedent already set by
    nearest_neighbors/get_edges_for_concept's own brute-force scans)."""
    pages = {}
    if not wiki_dir.exists():
        return pages
    for path in wiki_dir.glob("*.md"):
        if path.stem in ("index", "log"):
            continue
        text = path.read_text()
        # Check if this is an aspect page (forward-compat with PR #13):
        # aspect pages carry the same concept_id as their parent overview page
        # plus an `aspect_of` key, so we must skip them to avoid ambiguity.
        if _has_aspect_of(text):
            continue
        # Wiki pages are user-editable output — a hand-edited/corrupt
        # frontmatter line (e.g. an unquoted `term:` value) must not abort
        # the whole compile run. Treat an unparseable page as "no existing
        # page": the concept will simply be regenerated under a fresh slug.
        try:
            frontmatter = parse_wiki_page_frontmatter(text)
        except ValueError:  # json.JSONDecodeError is a ValueError subclass
            logger.warning("Skipping unparseable wiki page frontmatter: %s", path)
            continue
        if frontmatter and "concept_id" in frontmatter:
            pages[frontmatter["concept_id"]] = {"slug": path.stem, "frontmatter": frontmatter}
    return pages


def _has_aspect_of(text: str) -> bool:
    """Check if the frontmatter contains an aspect_of key."""
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 2:
        return False
    for line in parts[1].strip().splitlines():
        if line.strip().startswith("aspect_of"):
            return True
    return False


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


def _resolve_aspects(wiki_dir: Path, aspect_slugs: list[str]) -> list[dict]:
    """slug -> {"slug", "term"} for each aspect slug recorded in an overview
    page's frontmatter. Tolerates a missing or unparseable aspect file (skips
    it) rather than failing the whole page lookup — same tolerance
    scan_wiki_pages applies to overview pages."""
    resolved = []
    for slug in aspect_slugs:
        path = wiki_dir / f"{slug}.md"
        if not path.exists():
            continue
        try:
            frontmatter = parse_wiki_page_frontmatter(path.read_text())
        except ValueError:
            continue
        resolved.append({"slug": slug, "term": (frontmatter or {}).get("term", slug)})
    return resolved


def get_wiki_page_by_concept_id(wiki_dir: Path, concept_id: str) -> dict | None:
    """Read-only lookup for the frontend's wiki panel: the compiled overview
    page for one concept, plus its aspect pages' {slug, term} (empty list on
    any page compiled before PR #13's aspect-split feature, or on a concept
    that hasn't been split). Returns None if the concept has no wiki page
    yet — the wiki compile layer only generates one once
    MIN_PROVENANCE_COUNT is met (see app.wiki.selection), so this is an
    expected, common case, not an error."""
    pages = scan_wiki_pages(wiki_dir)
    match = pages.get(concept_id)
    if match is None:
        return None
    frontmatter = match["frontmatter"]
    body = extract_body((wiki_dir / f"{match['slug']}.md").read_text())
    return {
        "slug": match["slug"],
        "term": frontmatter.get("term", concept_id),
        "updated_at": frontmatter.get("updated_at", ""),
        "body": body,
        "aspects": _resolve_aspects(wiki_dir, frontmatter.get("aspects", [])),
    }


def get_wiki_page_by_slug(wiki_dir: Path, slug: str) -> dict | None:
    """Read-only lookup for one wiki page file by its filename slug, used to
    fetch an *aspect* sub-page's body — aspect pages share their parent's
    concept_id (see scan_wiki_pages' exclusion of them), so they can't be
    looked up unambiguously by concept_id and need this slug-keyed path
    instead. Works for overview pages too (same underlying file), but the
    frontend only ever calls this for aspects."""
    path = wiki_dir / f"{slug}.md"
    if not path.exists():
        return None
    text = path.read_text()
    try:
        frontmatter = parse_wiki_page_frontmatter(text) or {}
    except ValueError:
        return None
    return {
        "slug": slug,
        "term": frontmatter.get("term", slug),
        "updated_at": frontmatter.get("updated_at", ""),
        "body": extract_body(text),
        "aspects": [],
    }
