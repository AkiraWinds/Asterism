import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.concept_graph.pipeline import process_highlight
from app.graph_store.store import graph_db_path, init_db, list_concepts, list_edges, list_review_queue
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
