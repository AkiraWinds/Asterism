"""Markdown rendering for wiki pages, index.md, and log.md entries.
Frontmatter is hand-rolled `key: json.dumps(value)` lines (no PyYAML
dependency), matching the pattern already used for content.md's title
frontmatter in app.repositories.source_repository."""

import json

_FRONTMATTER_KEYS = (
    "concept_id", "term", "updated_at", "source_highlight_count",
    "source_provenance_hash", "source_ids",
)


def render_wiki_page(
    concept_id: str, term: str, updated_at: str, source_highlight_count: int,
    source_provenance_hash: str, source_ids: list[str], body: str,
    related_section: str, sources_section: str,
) -> str:
    frontmatter_lines = [
        f"concept_id: {json.dumps(concept_id)}",
        f"term: {json.dumps(term)}",
        f"updated_at: {json.dumps(updated_at)}",
        f"source_highlight_count: {json.dumps(source_highlight_count)}",
        f"source_provenance_hash: {json.dumps(source_provenance_hash)}",
        f"source_ids: {json.dumps(source_ids)}",
    ]
    parts = ["---", *frontmatter_lines, "---", "", body.strip(), ""]
    if related_section:
        parts.append(related_section.strip())
        parts.append("")
    if sources_section:
        parts.append(sources_section.strip())
        parts.append("")
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
