"""Prompt assembly and response parsing for wiki page synthesis — turns one
concept's linked highlight/source citations and edges into a grounded prose
page. See docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md."""

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
    parts.append('Respond with JSON only: {"synthesis": "<the prose>"}')
    return "\n\n".join(parts)


def parse_wiki_page_response(raw: str) -> str:
    try:
        parsed = json.loads(_strip_markdown_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed wiki page response: {exc}") from exc
    if not isinstance(parsed, dict) or "synthesis" not in parsed:
        raise ValueError(f"Wiki page response missing 'synthesis' key: {raw!r}")
    return parsed["synthesis"]
