"""Prompt assembly and response parsing for concept extraction and dedup
judgment. Prompt wording follows the validated draft in
docs/updates/plans/7-25-phase1-prompt-validation.md (local-only): extraction
weighs a user's note as the primary signal for *why* a passage matters, and
dedup treats a note-asserted relationship as always-high-confidence even when
raw embedding similarity alone would be borderline (that doc's finding #2).
"""

import json


def build_extraction_prompt(source_quote: str, note: str | None) -> str:
    parts = [
        "You are extracting concept nodes for a personal knowledge graph. "
        "Given a highlighted passage from a source, and an optional user note "
        "explaining why they highlighted it, extract 1-3 concepts. For each: a "
        "short name (2-5 words), a definition (1-2 sentences, grounded in the "
        "passage), whether it is self-relevant (the note references the user's "
        "own project/work rather than another source concept), and — if a note "
        "is present and does NOT indicate self-relevance — what relationship it "
        "signals to something else: contradicts, extends, related_to, or none.",
        f"## Highlighted passage\n\n{source_quote}",
    ]
    if note:
        parts.append(f"## User's note\n\n{note}")
    parts.append(
        "Respond with JSON only: a list of objects with keys term, definition, "
        "self_relevant (bool), relationship (one of contradicts/extends/related_to/none)."
    )
    return "\n\n".join(parts)


def parse_extraction_response(raw: str) -> list[dict]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed extraction response: {exc}") from exc


def build_dedup_prompt(
    candidate_term: str, candidate_definition: str, candidate_note: str | None, neighbors: list[dict]
) -> str:
    neighbor_lines = "\n".join(f"- {n['id']}: {n['term']} — {n['definition']}" for n in neighbors)
    parts = [
        "You are deduplicating concept nodes in a personal knowledge graph. "
        "Compare the candidate concept below against each existing neighbor and "
        "judge whether it is the same concept, related-but-distinct, or genuinely new. "
        "IMPORTANT: if the candidate's note explicitly asserts a relationship to a "
        "neighbor (e.g. 'same idea as X but more specific'), that note's assertion "
        "should override an otherwise-ambiguous embedding similarity score and count "
        "as high confidence — do not downgrade confidence just because the definitions "
        "alone look different.",
        f"## Candidate concept\n\n{candidate_term}: {candidate_definition}",
    ]
    if candidate_note:
        parts.append(f"## Candidate's note\n\n{candidate_note}")
    parts.append(f"## Existing neighbors\n\n{neighbor_lines}")
    parts.append(
        "Respond with JSON only: a list of objects with keys existing_concept_id, "
        "judgment (one of same/related_distinct/new), confidence (high/medium), summary."
    )
    return "\n\n".join(parts)


def parse_dedup_response(raw: str) -> list[dict]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed dedup response: {exc}") from exc
