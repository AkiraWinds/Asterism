"""Markdown rendering for wiki pages, index.md, and log.md entries.
Frontmatter is hand-rolled `key: json.dumps(value)` lines (no PyYAML
dependency), matching the pattern already used for content.md's title
frontmatter in app.repositories.source_repository."""

import json

_FRONTMATTER_KEYS = (
    "concept_id", "term", "updated_at", "source_highlight_count",
    "source_provenance_hash", "source_ids", "aspects", "aspect_of",
)


def render_wiki_page(
    concept_id: str, term: str, updated_at: str, source_highlight_count: int,
    source_provenance_hash: str, source_ids: list[str], body: str,
    related_section: str, sources_section: str, aspects: list[str] | None = None,
) -> str:
    frontmatter_lines = [
        f"concept_id: {json.dumps(concept_id)}",
        f"term: {json.dumps(term)}",
        f"updated_at: {json.dumps(updated_at)}",
        f"source_highlight_count: {json.dumps(source_highlight_count)}",
        f"source_provenance_hash: {json.dumps(source_provenance_hash)}",
        f"source_ids: {json.dumps(source_ids)}",
    ]
    if aspects:
        frontmatter_lines.append(f"aspects: {json.dumps(aspects)}")
    parts = ["---", *frontmatter_lines, "---", "", body.strip(), ""]
    if related_section:
        parts.append(related_section.strip())
        parts.append("")
    if sources_section:
        parts.append(sources_section.strip())
        parts.append("")
    return "\n".join(parts)


def render_aspect_page(
    concept_id: str, term: str, aspect_of: str, updated_at: str, source_ids: list[str], body: str,
) -> str:
    """Renders one aspect page. No source_provenance_hash/source_highlight_count
    of its own — aspect pages are always regenerated as a group alongside
    their overview (see compile.py), staleness is decided once at the
    concept level, not per aspect."""
    frontmatter_lines = [
        f"concept_id: {json.dumps(concept_id)}",
        f"term: {json.dumps(term)}",
        f"aspect_of: {json.dumps(aspect_of)}",
        f"updated_at: {json.dumps(updated_at)}",
        f"source_ids: {json.dumps(source_ids)}",
    ]
    parts = ["---", *frontmatter_lines, "---", "", body.strip(), ""]
    return "\n".join(parts)


def parse_wiki_page_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        if key not in _FRONTMATTER_KEYS:
            continue
        frontmatter[key] = json.loads(raw_value.strip())
    return frontmatter or None


def extract_body(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2].lstrip("\n") if len(parts) >= 3 else text


def extract_synthesis_body(text: str) -> str:
    """Like `extract_body`, but stops at the first `## `-prefixed heading
    (the start of the Related concepts / Sources sections), returning only
    the LLM-synthesized prose. Used when re-reading an unchanged page back
    into `page_bodies` for the contradiction lint on a skip-path re-run:
    `render_related_section` always name-drops the other concept's term as
    link text, so feeding the full body (via `extract_body`) into the
    substring-based contradiction heuristic would make it fire on every
    re-run regardless of whether the synthesis prose itself ever mentioned
    the contradiction."""
    body = extract_body(text)
    idx = body.find("\n## ")
    return body if idx == -1 else body[:idx]


def render_related_section(
    edges: list[dict], concept_terms: dict[str, str], concept_slugs: dict[str, str], self_id: str,
) -> str:
    if not edges:
        return ""
    lines = ["## Related concepts", ""]
    for edge in edges:
        other_id = edge["to_id"] if edge["from_id"] == self_id else edge["from_id"]
        other_term = concept_terms.get(other_id, other_id)
        target = f"[{other_term}](./{concept_slugs[other_id]}.md)" if other_id in concept_slugs else other_term
        lines.append(f"- **{edge['type']}** {target} — {edge['summary']}")
    return "\n".join(lines) + "\n"


def render_sources_section(citations: list[dict]) -> str:
    if not citations:
        return ""
    lines = ["## Sources", ""]
    for citation in citations:
        if citation["quote"] is not None:
            lines.append(f"- {citation['label']} — \"{citation['quote']}\"")
        else:
            lines.append(f"- {citation['label']}")
    return "\n".join(lines) + "\n"


_DEFINITION_TRUNCATE_LEN = 150


def render_index(pages: list[dict], attention_items: list[str]) -> str:
    lines = ["# Wiki Index", ""]
    for page in pages:
        date = page["updated_at"][:10]
        # Definitions are free-form user/AI text and may contain newlines
        # (which would break a markdown list item) or run long; collapse
        # whitespace and cap length so the index stays one line per entry.
        definition = " ".join(page["definition"].split())
        if len(definition) > _DEFINITION_TRUNCATE_LEN:
            definition = definition[:_DEFINITION_TRUNCATE_LEN].rstrip() + "…"
        lines.append(
            f"- [{page['term']}]({page['slug']}.md) — {definition} · "
            f"{page['source_highlight_count']} highlights · updated {date}"
        )
        for aspect in page.get("aspect_pages", []):
            lines.append(f"  - [{aspect['term']}]({aspect['slug']}.md)")
    if attention_items:
        lines += ["", "## Needs attention", ""]
        lines += [f"- {item}" for item in attention_items]
    return "\n".join(lines) + "\n"


def render_log_entry(
    date: str, pages_updated: int, pages_new: int, orphans_flagged: int, errors_count: int,
    change_lines: list[str],
) -> str:
    header = (
        f"## [{date}] wiki-compile | {pages_updated} pages updated, {pages_new} new, "
        f"{orphans_flagged} orphans flagged, {errors_count} errors"
    )
    lines = [header, *change_lines]
    # Trailing blank line (not just a single "\n") so consecutive entries
    # appended to log.md over multiple runs stay visually separated instead
    # of the next run's header landing immediately after this entry's last
    # change line.
    return "\n".join(lines) + "\n\n"
