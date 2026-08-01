import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.concept_graph.pipeline import (
    _complete_with_retry,
    process_highlight,
    promote_concept,
    _RELATIONSHIP_TO_EDGE_TYPE,
)
from app.concept_graph.prompts import parse_extraction_response
from app.graph_store.store import graph_db_path, init_db, list_concepts, list_edges, list_review_queue
from app.providers.base import Provider, ProviderConfigError
from app.schemas.analysis import Concept
from app.schemas.highlight import Highlight


def _make_highlight(quote="the AI reads first", note=None) -> Highlight:
    return Highlight(id="h_1", source_quote=quote, note=note, source_title="Test Source", created_at="2026-07-30T00:00:00Z")


class _FlakyThenGoodProvider(Provider):
    """Returns malformed JSON once, then a valid response — for retry tests."""

    def __init__(self, good_response: str):
        self._good_response = good_response
        self._calls = 0

    def complete(self, prompt: str) -> str:
        self._calls += 1
        if self._calls == 1:
            return "not json"
        return self._good_response


class _AlwaysBadProvider(Provider):
    def complete(self, prompt: str) -> str:
        return "not json"


def test_complete_with_retry_succeeds_on_second_attempt():
    good = json.dumps([{"term": "RAG", "definition": "def", "self_relevant": False}])
    provider = _FlakyThenGoodProvider(good)

    result = _complete_with_retry(provider, "prompt", parse_extraction_response)

    assert result[0]["term"] == "RAG"


def test_complete_with_retry_raises_after_max_attempts():
    provider = _AlwaysBadProvider()

    with pytest.raises(ValueError):
        _complete_with_retry(provider, "prompt", parse_extraction_response)


def test_process_highlight_creates_new_concept_when_no_neighbors_exist(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "AI-first triage", "definition": "AI processes first.", "self_relevant": False}
    ])

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert result.concepts[0].term == "AI-first triage"
    assert list_concepts(db_path)[0]["term"] == "AI-first triage"
    assert result.edges == []
    assert result.queued == []


def test_process_highlight_maps_related_to_relationship_to_related_edge_type(tmp_path: Path):
    # Task 5 (2026-08-01): The parser now rejects invalid relationship values
    # before they reach the pipeline (see _validate_dedup_enums in prompts.py).
    # This test was originally verifying that the pipeline's fallback would
    # convert unknown values to "related" — but that scenario no longer occurs.
    # The fallback remains as defense-in-depth in _RELATIONSHIP_TO_EDGE_TYPE,
    # but testing it requires a valid relationship value. Using "related_to"
    # (valid) to verify the happy path; the enum validation is tested in
    # test_concept_graph_prompts.py.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high",
                      "relationship": "related_to", "summary": "related"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is None
    assert len(result.edges) == 1
    assert result.edges[0].type == "related"


def test_relationship_to_edge_type_falls_back_to_related_for_unknown_key():
    # The defense-in-depth fallback in _RELATIONSHIP_TO_EDGE_TYPE.get(..., "related")
    # ensures that any unmapped relationship value (which should never occur due to
    # _validate_dedup_enums in prompts.py) gracefully converts to "related".
    assert _RELATIONSHIP_TO_EDGE_TYPE.get("some_unmapped_key", "related") == "related"
    assert _RELATIONSHIP_TO_EDGE_TYPE.get("unknown_relationship", "related") == "related"
    # Also verify that mapped keys still work as expected.
    assert _RELATIONSHIP_TO_EDGE_TYPE.get("related_to", "related") == "related"
    assert _RELATIONSHIP_TO_EDGE_TYPE.get("extends", "related") == "extends"
    assert _RELATIONSHIP_TO_EDGE_TYPE.get("contradicts", "related") == "contradicts"


def test_process_highlight_creates_edge_on_high_confidence_related_distinct(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "Filesystem is source of truth.", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Original vs. derived data model", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high",
                      "relationship": "extends", "summary": "related, note confirms"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(
            tmp_path, "source_a", _make_highlight(note="same idea but more specific"), provider, "sk-embed"
        )

    assert len(result.concepts) == 1
    assert len(result.edges) == 1
    assert result.edges[0].type == "extends"
    assert list_edges(db_path)[0]["type"] == "extends"
    assert result.queued == []


def test_process_highlight_forces_contradicts_into_review_queue_despite_high_confidence(tmp_path: Path):
    # Even at high dedup confidence, a "contradicts" classification must not
    # auto-apply as an edge — see the 2026-07-31 amendment: a human-in-the-loop
    # KG-QA study (arXiv:2602.05512) found 86.5% of LLM-flagged contradictions
    # were false positives once context was properly considered, so
    # "contradicts" always routes to the review queue regardless of confidence.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "X theory", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Anti-X theory", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high",
                      "relationship": "contradicts", "summary": "these two claims conflict"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.edges == []
    assert len(result.queued) == 1
    assert result.queued[0].proposed_edge_type == "contradicts"
    assert list_review_queue(db_path)[0]["proposed_edge_type"] == "contradicts"


def test_process_highlight_queues_medium_confidence_instead_of_creating_edge(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Triage Card scoring", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Personalized feed ranking", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "medium",
                      "relationship": "related_to", "summary": "both ranking mechanisms"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.15, 0.2]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert len(result.concepts) == 1
    assert result.edges == []
    assert len(result.queued) == 1
    assert list_review_queue(db_path)[0]["llm_judgment"] == "both ranking mechanisms"
    assert list_review_queue(db_path)[0]["proposed_edge_type"] == "related"


def test_process_highlight_merges_on_same_judgment_without_new_concept(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "AI-first triage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "AI-first triage", "definition": "def restated", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "same", "confidence": "high",
                      "relationship": "none", "summary": "identical"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.concepts == []
    assert len(list_concepts(db_path)) == 1
    assert result.edges == []


def test_process_highlight_sets_extraction_error_on_malformed_response(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.return_value = "not json"

    result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is not None
    assert result.concepts == []
    assert list_concepts(db_path) == []


def test_process_highlight_creates_new_concept_on_new_judgment_with_neighbors(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Unrelated topic", "def", [0.9, 0.9], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Brand new concept", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "new", "confidence": "high",
                      "relationship": "none", "summary": "unrelated"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert result.concepts[0].term == "Brand new concept"
    assert len(list_concepts(db_path)) == 2
    assert result.edges == []
    assert result.queued == []


def test_process_highlight_sets_extraction_error_on_malformed_dedup_response(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False}]),
        # Dedup response is malformed on both attempts — _complete_with_retry
        # retries once (MAX_ATTEMPTS=2) before giving up.
        "not json",
        "not json",
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is not None
    assert result.concepts == []
    assert result.edges == []
    assert result.queued == []
    # Only the pre-seeded existing concept should remain — nothing new got committed.
    assert len(list_concepts(db_path)) == 1


def test_process_highlight_sets_extraction_error_on_provider_error_during_extraction(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.side_effect = ProviderConfigError("Error code: 401 - invalid x-api-key")

    result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is not None
    assert "401" in result.extraction_error
    assert result.concepts == []
    assert result.edges == []
    assert result.queued == []
    assert list_concepts(db_path) == []


def test_process_highlight_sets_extraction_error_on_empty_dedup_judgments(tmp_path: Path):
    # An empty JSON list `[]` passes _validate_shape (nothing to check per-item)
    # but `judgments[0]` would previously raise an unhandled IndexError instead
    # of degrading like every other malformed-LLM-output case.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False}]),
        json.dumps([]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is not None
    assert result.concepts == []
    assert len(list_concepts(db_path)) == 1


def test_process_highlight_prefers_same_judgment_over_earlier_new_judgment(tmp_path: Path):
    # The dedup prompt returns one judgment per neighbor considered. If an
    # earlier neighbor in the list was judged "new" but a later neighbor was
    # judged "same" (a real duplicate), the pipeline must not silently pick
    # the first entry and create a duplicate concept — the "same" judgment
    # anywhere in the list must win.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_other", "Some other concept", "def", [0.5, 0.5], False, "2026-07-30T00:00:00Z")
    insert_concept(db_path, "c_existing", "AI-first triage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "AI-first triage", "definition": "def restated", "self_relevant": False}]),
        json.dumps([
            {"existing_concept_id": "c_other", "judgment": "new", "confidence": "high",
             "relationship": "none", "summary": "unrelated"},
            {"existing_concept_id": "c_existing", "judgment": "same", "confidence": "high",
             "relationship": "none", "summary": "identical"},
        ]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is None
    assert result.concepts == []
    # No new concept should have been created — only the two pre-seeded ones remain.
    assert len(list_concepts(db_path)) == 2
    # The highlight should be linked to the existing duplicate, not a new concept.
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT concept_id FROM concept_highlights WHERE highlight_id = ?", (_make_highlight().id,)).fetchall()
    assert [r["concept_id"] for r in rows] == ["c_existing"]


def test_process_highlight_sets_extraction_error_on_unknown_existing_concept_id(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_does_not_exist", "judgment": "same", "confidence": "high",
                      "relationship": "none", "summary": "hallucinated id"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is not None
    assert result.concepts == []
    assert len(list_concepts(db_path)) == 1


def test_process_highlight_handles_empty_extraction_as_no_op(tmp_path: Path):
    # Task 7 (2026-08-01): the rewritten extraction prompt permits the LLM to
    # abstain with "[]" when nothing in the passage clears the bar. This
    # confirms that path is a clean no-op through the whole pipeline
    # (extraction -> _dedupe_and_insert's `for item in items` loop simply not
    # executing) rather than a crash or spurious extraction_error.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.return_value = "[]"

    result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is None
    assert result.concepts == []
    assert result.edges == []
    assert result.queued == []
    assert list_concepts(db_path) == []


from app.concept_graph.pipeline import process_source_concepts
from app.schemas.analysis import Concept


def test_process_source_concepts_creates_new_concepts_with_no_neighbors(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.return_value = json.dumps([])  # no dedup call needed (no neighbors)

    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]):
        concepts, edges, queued, error = process_source_concepts(
            tmp_path, "source_a",
            [Concept(id="dc_1", term="RAG", definition="Retrieval-augmented generation.")],
            provider, "sk-embed",
        )

    assert error is None
    assert len(concepts) == 1
    assert concepts[0].term == "RAG"
    assert concepts[0].self_relevant is False
    stored = list_concepts(db_path)
    assert len(stored) == 1
    assert stored[0]["self_relevant"] == 0
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT concept_id, source_id FROM concept_sources").fetchall()
    assert [(r["concept_id"], r["source_id"]) for r in rows] == [(concepts[0].id, "source_a")]


def test_process_source_concepts_skips_extraction_llm_call(tmp_path: Path):
    # Phase 4's analysis pipeline already produced term/definition — no
    # extraction LLM call should happen, only dedup (and here, not even
    # that, since there are no existing concepts to compare against).
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()

    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]):
        process_source_concepts(
            tmp_path, "source_a",
            [Concept(id="dc_1", term="RAG", definition="def")],
            provider, "sk-embed",
        )

    provider.complete.assert_not_called()


def test_process_source_concepts_links_same_match_via_concept_sources(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "RAG", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"existing_concept_id": "c_existing", "judgment": "same", "confidence": "high",
         "relationship": "none", "summary": "identical"}
    ])

    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]):
        concepts, edges, queued, error = process_source_concepts(
            tmp_path, "source_a",
            [Concept(id="dc_1", term="RAG", definition="def restated")],
            provider, "sk-embed",
        )

    assert error is None
    assert concepts == []
    assert len(list_concepts(db_path)) == 1
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT concept_id, source_id FROM concept_sources WHERE source_id = 'source_a'").fetchall()
    assert [r["concept_id"] for r in rows] == ["c_existing"]


def test_process_source_concepts_classifies_contradiction_between_two_sources(tmp_path: Path):
    # The core capability gap this task fixes: Tier-1 concepts have no note,
    # so relationship classification must come purely from the two
    # definitions — and "contradicts" must still be forced into the review
    # queue rather than auto-applied.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "X theory", "X is true.", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high",
         "relationship": "contradicts", "summary": "these conflict"}
    ])

    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.11, 0.19]):
        concepts, edges, queued, error = process_source_concepts(
            tmp_path, "source_b",
            [Concept(id="dc_2", term="Anti-X theory", definition="X is false.")],
            provider, "sk-embed",
        )

    assert error is None
    assert edges == []
    assert len(queued) == 1
    assert queued[0].proposed_edge_type == "contradicts"


def test_process_source_concepts_returns_error_on_provider_failure(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "RAG", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = ProviderConfigError("Error code: 401 - invalid x-api-key")

    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]):
        concepts, edges, queued, error = process_source_concepts(
            tmp_path, "source_a",
            [Concept(id="dc_1", term="Some concept", definition="def")],
            provider, "sk-embed",
        )

    assert error is not None
    assert "401" in error


def test_process_source_concepts_retry_does_not_duplicate_provenance_row(tmp_path: Path):
    # analyze is retryable (see analyze_source_endpoint), so process_source_concepts
    # can run more than once for the same source_id. The first run creates the
    # concept fresh (no neighbors); the second run then sees that concept as a
    # neighbor and (via a mocked "same" dedup judgment) links to it again. Without
    # clearing prior concept_sources rows for this source_id first, the second run
    # would insert a second (concept_id, source_id) row.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.return_value = json.dumps([])  # first run: no neighbors, no dedup call

    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]):
        concepts, _, _, error = process_source_concepts(
            tmp_path, "source_a",
            [Concept(id="dc_1", term="RAG", definition="Retrieval-augmented generation.")],
            provider, "sk-embed",
        )
    assert error is None
    assert len(concepts) == 1
    concept_id = concepts[0].id

    # Second run: the concept from the first run is now a neighbor, so dedup
    # gets called; mock it to judge "same" (the realistic no-op-content case).
    provider.complete.return_value = json.dumps([
        {"existing_concept_id": concept_id, "judgment": "same", "confidence": "high",
         "relationship": "none", "summary": "identical"}
    ])
    with patch("app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.2]):
        concepts2, _, _, error2 = process_source_concepts(
            tmp_path, "source_a",
            [Concept(id="dc_1", term="RAG", definition="Retrieval-augmented generation.")],
            provider, "sk-embed",
        )
    assert error2 is None
    assert concepts2 == []

    assert len(list_concepts(db_path)) == 1
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT concept_id, source_id FROM concept_sources WHERE source_id = 'source_a'"
        ).fetchall()
    assert [(r["concept_id"], r["source_id"]) for r in rows] == [(concept_id, "source_a")]


def test_promote_concept_creates_new_node_when_no_neighbors(tmp_path, monkeypatch):
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])
    provider = MagicMock()
    highlight = Highlight(
        id="h_1", source_quote="AI processes information faster than humans.",
        source_title="T", created_at="2026-08-01T00:00:00Z",
    )
    concept = Concept(id="c1", term="AI-first triage", definition="AI processes information faster than humans.")

    result = promote_concept(tmp_path, "src_1", highlight, concept, provider, "sk-embed")

    assert len(result.concepts) == 1
    assert result.concepts[0].term == "AI-first triage"
    assert result.extraction_error is None
    provider.complete.assert_not_called()  # no extraction LLM call — term/definition already known


def test_promote_concept_stores_self_relevant_true(tmp_path, monkeypatch):
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])
    provider = MagicMock()
    highlight = Highlight(id="h_1", source_quote="def", source_title="T", created_at="2026-08-01T00:00:00Z")
    concept = Concept(id="c1", term="term", definition="def")

    promote_concept(tmp_path, "src_1", highlight, concept, provider, "sk-embed")

    from app.graph_store.store import graph_db_path, init_db
    import sqlite3
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT self_relevant FROM concepts").fetchone()
    assert row[0] == 1


def test_new_concept_uses_web_search_result_when_available(tmp_path, monkeypatch):
    # No existing concepts in the graph, so nearest_neighbors returns [] and
    # the `if not neighbors:` short-circuit in _dedupe_and_insert is the "new
    # concept" path exercised here (same path as
    # test_process_highlight_creates_new_concept_when_no_neighbors_exist).
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.concept_graph.pipeline.search_web",
        lambda api_key, query, count=3: [
            {"title": "AI-first triage", "url": "https://example.com/ai-first-triage",
             "description": "A grounded, real-world description of AI-first triage."}
        ],
    )
    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "AI-first triage", "definition": "AI processes first.", "self_relevant": False}
    ])

    result = process_highlight(
        tmp_path, "source_a", _make_highlight(), provider, "sk-embed", brave_api_key="sk-brave",
    )

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert "grounded, real-world description" in result.concepts[0].definition
    assert "https://example.com/ai-first-triage" in result.concepts[0].definition
    assert "AI processes first." not in result.concepts[0].definition


def test_new_concept_keeps_extraction_definition_when_no_brave_key(tmp_path, monkeypatch):
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])
    search_web_mock = MagicMock()
    monkeypatch.setattr("app.concept_graph.pipeline.search_web", search_web_mock)
    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "AI-first triage", "definition": "AI processes first.", "self_relevant": False}
    ])

    result = process_highlight(
        tmp_path, "source_a", _make_highlight(), provider, "sk-embed", brave_api_key=None,
    )

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert result.concepts[0].definition == "AI processes first."
    search_web_mock.assert_not_called()


def test_new_concept_keeps_extraction_definition_when_web_search_returns_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])
    monkeypatch.setattr("app.concept_graph.pipeline.search_web", lambda api_key, query, count=3: [])
    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "AI-first triage", "definition": "AI processes first.", "self_relevant": False}
    ])

    result = process_highlight(
        tmp_path, "source_a", _make_highlight(), provider, "sk-embed", brave_api_key="sk-brave",
    )

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert result.concepts[0].definition == "AI processes first."


def test_grounded_concept_persists_embedding_computed_from_grounded_definition(tmp_path, monkeypatch):
    # Whole-branch review finding #1: `embedding = embed_text(..., item["definition"])`
    # ran on the pre-grounding definition, but the concept got persisted with
    # the GROUNDED definition alongside that stale embedding — desyncing
    # nearest_neighbors matching for every grounded concept. Guard against
    # regression by using an embed_text stub whose output depends on its
    # input text, so a mismatch between persisted definition and persisted
    # embedding is detectable.
    def fake_embed_text(api_key, text):
        return [float(len(text)), 0.0]

    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", fake_embed_text)
    monkeypatch.setattr(
        "app.concept_graph.pipeline.search_web",
        lambda api_key, query, count=3: [
            {"title": "AI-first triage", "url": "https://example.com/ai-first-triage",
             "description": "A grounded, real-world description of AI-first triage."}
        ],
    )
    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "AI-first triage", "definition": "AI processes first.", "self_relevant": False}
    ])

    result = process_highlight(
        tmp_path, "source_a", _make_highlight(), provider, "sk-embed", brave_api_key="sk-brave",
    )

    from app.graph_store.store import get_concept
    db_path = graph_db_path(tmp_path)
    stored = get_concept(db_path, result.concepts[0].id)
    grounded_definition = stored["definition"]
    assert "grounded, real-world description" in grounded_definition

    expected_embedding = fake_embed_text("sk-embed", grounded_definition)
    assert stored["embedding"] == expected_embedding
    # The bug this guards against: persisting the embedding computed from
    # the ORIGINAL pre-grounding definition instead.
    assert stored["embedding"] != fake_embed_text("sk-embed", "AI processes first.")


def test_self_relevant_new_concept_skips_web_search_grounding(tmp_path, monkeypatch):
    # Human decision: self_relevant concepts describe the user's OWN
    # project/work, so grounding them via web search risks replacing a
    # correct extraction-time definition with an unrelated one (e.g.
    # "Asterism" the project vs. the star cluster).
    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.2])
    search_web_mock = MagicMock(return_value=[
        {"title": "t", "url": "https://example.com", "description": "unrelated grounded description"}
    ])
    monkeypatch.setattr("app.concept_graph.pipeline.search_web", search_web_mock)
    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "Asterism", "definition": "The user's own knowledge-management project.", "self_relevant": True}
    ])

    result = process_highlight(
        tmp_path, "source_a", _make_highlight(), provider, "sk-embed", brave_api_key="sk-brave",
    )

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert result.concepts[0].definition == "The user's own knowledge-management project."
    search_web_mock.assert_not_called()


def test_related_distinct_new_concept_is_grounded_via_web_search(tmp_path, monkeypatch):
    # Whole-branch review finding #7: grounding was applied on the
    # "no neighbors" and judgment == "new" branches but NOT on
    # judgment == "related_distinct", even though that branch also creates a
    # brand-new concept per the design doc.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "Filesystem is source of truth.", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    monkeypatch.setattr("app.concept_graph.pipeline.embed_text", lambda api_key, text: [0.1, 0.21])
    monkeypatch.setattr(
        "app.concept_graph.pipeline.search_web",
        lambda api_key, query, count=3: [
            {"title": "t", "url": "https://example.com/original-vs-derived",
             "description": "A grounded description of original vs derived data."}
        ],
    )
    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Original vs. derived data model", "definition": "def", "self_relevant": False}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high",
                      "relationship": "extends", "summary": "related, note confirms"}]),
    ]

    result = process_highlight(
        tmp_path, "source_a", _make_highlight(note="same idea but more specific"), provider, "sk-embed",
        brave_api_key="sk-brave",
    )

    assert result.extraction_error is None
    assert len(result.concepts) == 1
    assert "grounded description of original vs derived data" in result.concepts[0].definition
    assert result.concepts[0].definition != "def"
