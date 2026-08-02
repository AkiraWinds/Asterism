"""Decides which concepts have enough linked provenance to earn a wiki page."""

MIN_PROVENANCE_COUNT = 3


def select_qualifying_concepts(concepts: list[dict], provenance_by_concept: dict[str, list[dict]]) -> list[dict]:
    # Golden concepts (user-approved via the watchlist, see app/routers/watchlist.py)
    # are user-declared rather than extracted from sources, so they legitimately
    # have zero provenance links and would otherwise never clear
    # MIN_PROVENANCE_COUNT. Per human decision: bypass the provenance threshold
    # for golden concepts — the user's explicit approval stands in for it.
    return [
        c for c in concepts
        if c.get("golden") or len(provenance_by_concept.get(c["id"], [])) >= MIN_PROVENANCE_COUNT
    ]
