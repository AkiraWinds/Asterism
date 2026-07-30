import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.concept_graph.pipeline import process_highlight
from app.graph_store.store import graph_db_path, init_db, list_concepts, list_edges, list_review_queue
from app.providers.base import ProviderConfigError
from app.schemas.highlight import Highlight


def _make_highlight(quote="the AI reads first", note=None) -> Highlight:
    return Highlight(id="h_1", source_quote=quote, note=note, source_title="Test Source", created_at="2026-07-30T00:00:00Z")


def test_process_highlight_creates_new_concept_when_no_neighbors_exist(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)

    provider = MagicMock()
    provider.complete.return_value = json.dumps([
        {"term": "AI-first triage", "definition": "AI processes first.", "self_relevant": False, "relationship": "none"}
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


def test_process_highlight_falls_back_to_related_edge_type_for_unknown_relationship(tmp_path: Path):
    # `_RELATIONSHIP_TO_EDGE_TYPE` is keyed on the extraction prompt's expected
    # relationship values, but the LLM can return anything as a raw string
    # (_validate_shape only checks key presence, not value membership). A
    # dict-index lookup would raise KeyError (uncaught) rather than degrading
    # like the other malformed-LLM-output cases — this must fall back to
    # "related" instead of crashing.
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False, "relationship": "related"}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high", "summary": "related"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is None
    assert len(result.edges) == 1
    assert result.edges[0].type == "related"


def test_process_highlight_creates_edge_on_high_confidence_related_distinct(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Local-first storage", "Filesystem is source of truth.", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Original vs. derived data model", "definition": "def", "self_relevant": False, "relationship": "extends"}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "high", "summary": "related, note confirms"}]),
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


def test_process_highlight_queues_medium_confidence_instead_of_creating_edge(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "Triage Card scoring", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "Personalized feed ranking", "definition": "def", "self_relevant": False, "relationship": "none"}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "related_distinct", "confidence": "medium", "summary": "both ranking mechanisms"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.15, 0.2]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert len(result.concepts) == 1
    assert result.edges == []
    assert len(result.queued) == 1
    assert list_review_queue(db_path)[0]["llm_judgment"] == "both ranking mechanisms"


def test_process_highlight_merges_on_same_judgment_without_new_concept(tmp_path: Path):
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    from app.graph_store.store import insert_concept
    insert_concept(db_path, "c_existing", "AI-first triage", "def", [0.1, 0.2], False, "2026-07-30T00:00:00Z")

    provider = MagicMock()
    provider.complete.side_effect = [
        json.dumps([{"term": "AI-first triage", "definition": "def restated", "self_relevant": False, "relationship": "none"}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "same", "confidence": "high", "summary": "identical"}]),
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
        json.dumps([{"term": "Brand new concept", "definition": "def", "self_relevant": False, "relationship": "none"}]),
        json.dumps([{"existing_concept_id": "c_existing", "judgment": "new", "confidence": "high", "summary": "unrelated"}]),
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
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False, "relationship": "none"}]),
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
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False, "relationship": "none"}]),
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
        json.dumps([{"term": "AI-first triage", "definition": "def restated", "self_relevant": False, "relationship": "none"}]),
        json.dumps([
            {"existing_concept_id": "c_other", "judgment": "new", "confidence": "high", "summary": "unrelated"},
            {"existing_concept_id": "c_existing", "judgment": "same", "confidence": "high", "summary": "identical"},
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
        json.dumps([{"term": "Some concept", "definition": "def", "self_relevant": False, "relationship": "none"}]),
        json.dumps([{"existing_concept_id": "c_does_not_exist", "judgment": "same", "confidence": "high", "summary": "hallucinated id"}]),
    ]

    with patch(
        "app.concept_graph.pipeline.embed_text", return_value=[0.1, 0.21]
    ):
        result = process_highlight(tmp_path, "source_a", _make_highlight(), provider, "sk-embed")

    assert result.extraction_error is not None
    assert result.concepts == []
    assert len(list_concepts(db_path)) == 1
