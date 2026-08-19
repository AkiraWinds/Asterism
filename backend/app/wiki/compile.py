# backend/app/wiki/compile.py
"""Orchestrates one wiki compile run: read graph.db, decide which qualifying
concepts need a (re)generated page, call the LLM only for new/changed ones,
write wiki/*.md + index.md + append a log.md entry, and fold in the
lightweight lint pass. graph.db stays the source of truth throughout — this
module only ever reads it. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, list_concepts, list_edges
from app.providers.base import Provider, ProviderError
from app.wiki.hashing import provenance_hash
from app.wiki.lint import find_orphan_concepts, find_unexplained_contradictions
from app.wiki.prompts import build_wiki_page_prompt, parse_wiki_page_response
from app.wiki.render import (
    extract_synthesis_body,
    parse_wiki_page_frontmatter,
    render_aspect_page,
    render_index,
    render_log_entry,
    render_related_section,
    render_sources_section,
    render_wiki_page,
)
from app.wiki.selection import select_qualifying_concepts
from app.wiki.slug import aspect_slug, unique_slug
from app.wiki.store_reader import get_concept_provenance, get_edges_for_concept, resolve_citations

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    # Codebase convention (see test fixtures) uses a trailing "Z" rather
    # than the "+00:00" offset isoformat() emits by default.
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scan_existing_pages(wiki_dir: Path) -> dict[str, dict]:
    """concept_id -> {"slug", "frontmatter"} for every existing wiki page, so
    re-runs keep the same slug/filename for the same concept instead of
    treating a concept's own prior page as a collision against itself."""
    pages = {}
    if not wiki_dir.exists():
        return pages
    for path in wiki_dir.glob("*.md"):
        if path.stem in ("index", "log"):
            continue
        # Wiki pages are user-editable output — a hand-edited/corrupt
        # frontmatter line (e.g. an unquoted `term:` value) must not abort
        # the whole compile run. Treat an unparseable page as "no existing
        # page": the concept will simply be regenerated under a fresh slug.
        try:
            frontmatter = parse_wiki_page_frontmatter(path.read_text())
        except ValueError:  # json.JSONDecodeError is a ValueError subclass
            logger.warning("Skipping unparseable wiki page frontmatter: %s", path)
            continue
        if frontmatter and "concept_id" in frontmatter and "aspect_of" not in frontmatter:
            pages[frontmatter["concept_id"]] = {"slug": path.stem, "frontmatter": frontmatter}
    return pages


def run_compile(data_root: Path, llm_provider: Provider) -> dict:
    db_path = graph_db_path(data_root)
    init_db(db_path)
    wiki_dir = data_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    concepts = list_concepts(db_path)
    all_edges = list_edges(db_path)
    concept_terms = {c["id"]: c["term"] for c in concepts}

    provenance_by_concept = {c["id"]: get_concept_provenance(db_path, c["id"]) for c in concepts}
    qualifying = select_qualifying_concepts(concepts, provenance_by_concept)

    existing_pages = _scan_existing_pages(wiki_dir)
    # Seed from every *.md file already on disk, not just the ones whose
    # frontmatter parsed cleanly — a corrupt/hand-edited page is still a
    # real file occupying its slug, and `_scan_existing_pages` skips adding
    # those to `existing_pages`. Without this, a fresh `unique_slug()` call
    # for the same concept (now treated as "no existing page") could pick
    # the corrupt file's own slug and overwrite it on write.
    taken_slugs = {"index", "log"} | {p.stem for p in wiki_dir.glob("*.md")}

    slug_by_concept_id: dict[str, str] = {}
    for concept in qualifying:
        if concept["id"] in existing_pages:
            slug_by_concept_id[concept["id"]] = existing_pages[concept["id"]]["slug"]
        else:
            slug = unique_slug(concept["term"], concept["id"], taken_slugs)
            taken_slugs.add(slug)
            slug_by_concept_id[concept["id"]] = slug

    pages_updated = 0
    pages_new = 0
    errors: list[dict] = []
    change_lines: list[str] = []
    page_bodies: dict[str, str] = {}
    page_meta: list[dict] = []

    for concept in qualifying:
        concept_id = concept["id"]
        slug = slug_by_concept_id[concept_id]
        page_path = wiki_dir / f"{slug}.md"
        provenance = provenance_by_concept[concept_id]
        current_hash = provenance_hash(provenance)

        existing = existing_pages.get(concept_id)
        is_new = existing is None
        # A page whose `updated_at` line was hand-deleted can still match on
        # source_provenance_hash; treat that as "not unchanged" so it falls
        # through to regeneration rather than raising KeyError.
        unchanged = (
            existing is not None
            and existing["frontmatter"].get("source_provenance_hash") == current_hash
            and "updated_at" in existing["frontmatter"]
        )

        if unchanged:
            page_bodies[concept_id] = extract_synthesis_body(page_path.read_text())
            # Aspect pages aren't independently hash-checked — staleness is
            # decided once at the concept level (see the provenance-hash
            # comparison above), so on an unchanged run we just re-read
            # whichever aspect files the last run wrote, keyed by the
            # overview's own recorded "aspects" slug list.
            aspect_pages_meta: list[dict] = []
            for existing_aspect_slug in existing["frontmatter"].get("aspects", []):
                aspect_path = wiki_dir / f"{existing_aspect_slug}.md"
                if not aspect_path.exists():
                    continue
                # Same invariant as `_scan_existing_pages`: a hand-edited/corrupt
                # aspect page must not abort the whole compile run.
                try:
                    aspect_frontmatter = parse_wiki_page_frontmatter(aspect_path.read_text())
                except ValueError:  # json.JSONDecodeError is a ValueError subclass
                    aspect_frontmatter = None
                aspect_term = aspect_frontmatter.get("term", existing_aspect_slug) if aspect_frontmatter else existing_aspect_slug
                aspect_pages_meta.append({"term": aspect_term, "slug": existing_aspect_slug})
            page_meta.append({
                "term": concept["term"], "slug": slug, "definition": concept["definition"],
                "source_highlight_count": len(provenance), "updated_at": existing["frontmatter"]["updated_at"],
                "aspect_pages": aspect_pages_meta,
            })
            continue

        concept_edges = get_edges_for_concept(db_path, concept_id)
        citations = resolve_citations(data_root, provenance)

        try:
            raw = llm_provider.complete(build_wiki_page_prompt(concept["term"], concept["definition"], citations, concept_edges))
            parsed_response = parse_wiki_page_response(raw)
        except (ValueError, ProviderError) as exc:
            logger.exception("Wiki compile failed for concept_id=%s", concept_id)
            errors.append({"concept_id": concept_id, "message": str(exc)})
            change_lines.append(f"- error: {concept['term']} — {exc}")
            continue

        body = parsed_response["overview"]
        for warning in parsed_response["warnings"]:
            logger.warning("Wiki compile aspect warning for concept_id=%s: %s", concept_id, warning)

        # Delete this concept's own previously-recorded aspect files before
        # writing the new set — the LLM re-decides the split fresh on every
        # regeneration (it's not a sticky decision), so the proposed aspects
        # can differ from last run's. Using the overview's own recorded slug
        # list (not a directory glob) means we only ever *consider* deleting
        # files that were once associated with this concept, never another
        # concept's page that happens to share a slug prefix. But a recorded
        # slug name alone isn't proof of current ownership: if that aspect
        # file was hand-deleted and a brand-new, unrelated concept later got
        # handed that exact freed slug by unique_slug()/aspect_slug(), an
        # unconditional discard()/unlink() here would silently reclaim or
        # destroy the new concept's real page. So re-verify ownership via the
        # file's own frontmatter (`aspect_of`/`concept_id`) before touching
        # it, and only ever free the slug when we can actually confirm it's
        # still ours or it's already gone.
        if existing is not None:
            for stale_aspect_slug in existing["frontmatter"].get("aspects", []):
                stale_path = wiki_dir / f"{stale_aspect_slug}.md"
                if not stale_path.exists():
                    continue  # already gone; if the slug is taken now it belongs to someone else, not ours to free
                try:
                    stale_frontmatter = parse_wiki_page_frontmatter(stale_path.read_text()) or {}
                except ValueError:  # json.JSONDecodeError is a ValueError subclass
                    continue  # unparseable — leave it alone, same tolerance as elsewhere in this module
                if stale_frontmatter.get("aspect_of") != slug or stale_frontmatter.get("concept_id") != concept_id:
                    continue  # ownership changed since we last recorded it — never delete another concept's page
                stale_path.unlink()
                taken_slugs.discard(stale_aspect_slug)

        source_ids = sorted({p["source_id"] for p in provenance})
        updated_at = _now_iso()

        aspect_slugs: list[str] = []
        aspect_pages_meta: list[dict] = []
        for aspect in parsed_response["aspects"]:
            this_aspect_slug = aspect_slug(slug, aspect["title"], taken_slugs)
            taken_slugs.add(this_aspect_slug)
            aspect_page_text = render_aspect_page(
                concept_id=concept_id, term=aspect["title"], aspect_of=slug,
                updated_at=updated_at, source_ids=source_ids, body=aspect["content"],
            )
            (wiki_dir / f"{this_aspect_slug}.md").write_text(aspect_page_text)
            aspect_slugs.append(this_aspect_slug)
            aspect_pages_meta.append({"term": aspect["title"], "slug": this_aspect_slug})

        page_text = render_wiki_page(
            concept_id=concept_id, term=concept["term"], updated_at=updated_at,
            source_highlight_count=len(provenance), source_provenance_hash=current_hash,
            source_ids=source_ids, body=body,
            related_section=render_related_section(concept_edges, concept_terms, slug_by_concept_id, concept_id),
            sources_section=render_sources_section(citations),
            aspects=aspect_slugs or None,
        )
        page_path.write_text(page_text)

        page_bodies[concept_id] = body
        page_meta.append({
            "term": concept["term"], "slug": slug, "definition": concept["definition"],
            "source_highlight_count": len(provenance), "updated_at": updated_at,
            "aspect_pages": aspect_pages_meta,
        })

        split_suffix = (
            f" (split into {1 + len(aspect_slugs)} pages: overview + {len(aspect_slugs)} "
            f"aspect{'s' if len(aspect_slugs) != 1 else ''})"
            if aspect_slugs else ""
        )
        if is_new:
            pages_new += 1
            change_lines.append(f"- new: {concept['term']}{split_suffix}")
        else:
            old_count = existing["frontmatter"].get("source_highlight_count", "?")
            pages_updated += 1
            change_lines.append(f"- updated: {concept['term']} ({old_count}→{len(provenance)} highlights){split_suffix}")

    # Only concepts with an actually-written page belong in orphan
    # detection: `slug_by_concept_id` is assigned before the LLM call, so it
    # still includes concepts whose generation failed this run — flagging
    # one of those as an orphan would link index.md to a .md file that was
    # never written.
    error_ids = {e["concept_id"] for e in errors}
    orphans = find_orphan_concepts(
        [c for c in qualifying if c["id"] not in error_ids], all_edges,
    )
    contradictions = find_unexplained_contradictions(
        [e for e in all_edges if e["type"] == "contradicts"], page_bodies, concept_terms,
    )

    attention_items = [
        f"Orphan: [{c['term']}]({slug_by_concept_id[c['id']]}.md) — no edges to any other concept"
        for c in orphans
    ]
    attention_items += [
        f"Unexplained contradiction: [{concept_terms[e['from_id']]}]({slug_by_concept_id[e['from_id']]}.md) "
        f"↔ [{concept_terms[e['to_id']]}]({slug_by_concept_id[e['to_id']]}.md) — {e['summary']}"
        for e in contradictions
        if e["from_id"] in slug_by_concept_id and e["to_id"] in slug_by_concept_id
    ]

    page_meta.sort(key=lambda p: p["updated_at"], reverse=True)
    (wiki_dir / "index.md").write_text(render_index(page_meta, attention_items))

    entry = render_log_entry(_now_iso()[:10], pages_updated, pages_new, len(orphans), len(errors), change_lines)
    with (wiki_dir / "log.md").open("a") as f:
        f.write(entry)

    return {"pages_updated": pages_updated, "pages_new": pages_new, "orphans_flagged": len(orphans), "errors": errors}
