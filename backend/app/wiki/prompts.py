"""Prompt assembly and response parsing for wiki page synthesis — turns one
concept's linked highlight/source citations and edges into a grounded prose
page, optionally split into an overview plus several aspect pages when the
concept's material covers genuinely distinct enough sub-topics. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md and
docs/superpowers/specs/2026-08-01-wiki-many-to-many-redesign-design.md."""

import json
import re


def _strip_markdown_fence(raw: str) -> str:
    """Same tolerance as app.concept_graph.prompts._strip_markdown_fence —
    duplicated rather than imported since that name is private to its module
    and this is 4 lines, not worth a cross-module coupling on a private
    helper."""
    match = re.match(r"^\s*```(?:json)?\s*\n(.*)\n\s*```\s*$", raw, re.DOTALL)
    return match.group(1) if match else raw


def build_wiki_page_prompt(term: str, definition: str, citations: list[dict], edges: list[dict]) -> str:
    parts = [
        "You are writing one page of a personal knowledge wiki for the concept "
        f'"{term}". Base definition: {definition}',
        "Write a short synthesis (1-3 paragraphs) grounded ONLY in the citations "
        "below — do not add outside knowledge beyond what they state or the base "
        "definition. If relationships to other concepts are listed, mention them "
        "explicitly in the prose (e.g. name what it contradicts or extends and why).",
    ]
    if citations:
        citation_lines = "\n".join(
            f'- {c["label"]}: "{c["quote"]}"' if c["quote"] else f'- {c["label"]}'
            for c in citations
        )
        parts.append(f"## Citations\n\n{citation_lines}")
    if edges:
        edge_lines = "\n".join(f"- {e['type']}: {e['summary']}" for e in edges)
        parts.append(f"## Relationships to other concepts\n\n{edge_lines}")
    parts.append(
        "Decide whether this concept's material covers one cohesive idea, or genuinely "
        "distinct enough aspects that they deserve separate pages (most concepts should "
        "NOT be split — only split when the aspects would each stand alone as useful pages).\n\n"
        "Respond with JSON only. If not splitting:\n"
        '{"synthesis": "<the prose>", "aspects": null}\n\n'
        "If splitting:\n"
        '{"synthesis": "<overview prose introducing the aspects>", '
        '"aspects": [{"title": "<short aspect title>", "content": "<aspect prose>"}, ...]}'
    )
    return "\n\n".join(parts)


def parse_wiki_page_response(raw: str) -> dict:
    """Returns {"overview": str, "aspects": list[{"title", "content"}], "warnings": list[str]}.
    A malformed individual aspect entry (or a non-list "aspects" value) is
    dropped with a warning rather than failing the whole response — the
    overview synthesis is still usable on its own. A missing/unparsable
    top-level response has no usable content at all, so that still raises."""
    try:
        parsed = json.loads(_strip_markdown_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed wiki page response: {exc}") from exc
    if not isinstance(parsed, dict) or "synthesis" not in parsed:
        raise ValueError(f"Wiki page response missing 'synthesis' key: {raw!r}")

    raw_aspects = parsed.get("aspects") or []
    warnings: list[str] = []
    if not isinstance(raw_aspects, list):
        warnings.append(f"'aspects' was not a list, ignoring: {raw_aspects!r}")
        raw_aspects = []

    aspects = []
    for item in raw_aspects:
        if isinstance(item, dict) and "title" in item and "content" in item:
            aspects.append({"title": item["title"], "content": item["content"]})
        else:
            warnings.append(f"malformed aspect entry ignored: {item!r}")

    return {"overview": parsed["synthesis"], "aspects": aspects, "warnings": warnings}
