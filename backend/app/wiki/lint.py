"""Lightweight lint checks folded into each wiki compile run: orphan
concepts (zero edges) and contradicts-edges neither endpoint's synthesized
page explains. Both are cheap heuristics over already-generated data — no
extra LLM calls, no separate lint command. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md."""


def find_orphan_concepts(concepts: list[dict], edges: list[dict]) -> list[dict]:
    touched = {e["from_id"] for e in edges} | {e["to_id"] for e in edges}
    return [c for c in concepts if c["id"] not in touched]


def find_unexplained_contradictions(
    edges: list[dict], page_bodies: dict[str, str], concept_terms: dict[str, str],
) -> list[dict]:
    flagged = []
    for edge in edges:
        if edge["type"] != "contradicts":
            continue
        from_body = page_bodies.get(edge["from_id"])
        to_body = page_bodies.get(edge["to_id"])
        if from_body is None or to_body is None:
            continue
        to_term = concept_terms.get(edge["to_id"], "")
        from_term = concept_terms.get(edge["from_id"], "")
        from_mentions_to = to_term.lower() in from_body.lower()
        to_mentions_from = from_term.lower() in to_body.lower()
        if not from_mentions_to and not to_mentions_from:
            flagged.append(edge)
    return flagged
