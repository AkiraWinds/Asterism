from pathlib import Path

from app.graph_store.store import graph_db_path, init_db, insert_concept, insert_watchlist_entry, get_watchlist_entry
from app.providers.base import Provider
from app.watchlist.resolver import resolve_watchlist_entry


class _StubProvider(Provider):
    def __init__(self, response: str):
        self._response = response
    def complete(self, prompt: str) -> str:
        return self._response


def test_resolve_matches_existing_concept_above_threshold(tmp_path: Path, monkeypatch):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "Agentic AI", "Existing grounded definition.", [1.0, 0.0], False, "2026-08-01T00:00:00Z")
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")

    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [1.0, 0.0])

    entry = resolve_watchlist_entry(tmp_path, "w_1", _StubProvider("unused"), "fake-embed-key", None)

    assert entry["draft_matched_concept_id"] == "c_1"
    assert entry["draft_definition"] is None


def test_resolve_falls_back_to_web_search_when_no_graph_match(tmp_path: Path, monkeypatch):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_watchlist_entry(db_path, "w_1", "Some brand new term", "2026-08-01T00:00:00Z")

    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    monkeypatch.setattr(
        "app.watchlist.resolver.search_web",
        lambda api_key, query, count=3: [{"title": "t", "url": "https://example.com", "description": "A grounded web definition."}],
    )

    entry = resolve_watchlist_entry(tmp_path, "w_1", _StubProvider("unused"), "fake-embed-key", "fake-brave-key")

    assert entry["draft_matched_concept_id"] is None
    assert "grounded web definition" in entry["draft_definition"]


def test_resolve_does_not_match_golden_concept_boosted_above_threshold_by_true_similarity_below_it(
    tmp_path: Path, monkeypatch,
):
    # Whole-branch review finding #3: nearest_neighbors' golden-bonus-boosted
    # ranking score must not leak into the resolver's absolute threshold
    # check. A golden concept at TRUE cosine similarity 0.81 gets a +0.05
    # ranking bonus (-> 0.86), which clears _MATCH_THRESHOLD (0.85) if the
    # resolver compares against the boosted score — but it must NOT be
    # treated as a match, since the true similarity (0.81) is below 0.85.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    # Embedding chosen so cosine_similarity([1.0, 0.0], embedding) == 0.81.
    insert_concept(
        db_path, "c_golden", "Some other term", "Existing def.", [0.81, (1 - 0.81 ** 2) ** 0.5],
        False, "2026-08-01T00:00:00Z", golden=True,
    )
    insert_watchlist_entry(db_path, "w_1", "Agentic AI", "2026-08-01T00:00:00Z")

    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [1.0, 0.0])

    entry = resolve_watchlist_entry(tmp_path, "w_1", _StubProvider("An LLM-drafted definition."), "fake-embed-key", None)

    # Not treated as a match: falls through to drafting a fresh definition
    # instead of pointing at the golden concept.
    assert entry["draft_matched_concept_id"] is None
    assert entry["draft_definition"] == "An LLM-drafted definition."


def test_resolve_falls_back_to_llm_reasoning_when_no_match_and_no_web_key(tmp_path: Path, monkeypatch):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_watchlist_entry(db_path, "w_1", "Some brand new term", "2026-08-01T00:00:00Z")

    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])

    entry = resolve_watchlist_entry(tmp_path, "w_1", _StubProvider("An LLM-drafted definition."), "fake-embed-key", None)

    assert entry["draft_matched_concept_id"] is None
    assert entry["draft_definition"] == "An LLM-drafted definition."
