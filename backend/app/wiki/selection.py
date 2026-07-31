"""Decides which concepts have enough linked provenance to earn a wiki page."""

MIN_PROVENANCE_COUNT = 3


def select_qualifying_concepts(concepts: list[dict], provenance_by_concept: dict[str, list[dict]]) -> list[dict]:
    return [c for c in concepts if len(provenance_by_concept.get(c["id"], [])) >= MIN_PROVENANCE_COUNT]
