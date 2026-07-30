# backend/tests/test_graph_schema.py
from app.schemas.graph import ConceptNode, Edge, GraphResponse, HighlightProcessResult, ReviewQueueEntry, ReviewQueueResolveRequest
from app.schemas.highlight import Highlight


def test_concept_node_defaults_self_relevant_false():
    c = ConceptNode(id="c_1", term="RAG", definition="Retrieval-augmented generation.")
    assert c.self_relevant is False


def test_edge_rejects_invalid_type():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Edge(id="e_1", from_id="c_1", to_id="c_2", type="invalid", summary="x")


def test_graph_response_holds_nodes_and_edges():
    node = ConceptNode(id="c_1", term="RAG", definition="def")
    edge = Edge(id="e_1", from_id="c_1", to_id="c_2", type="related", summary="s")
    resp = GraphResponse(nodes=[node], edges=[edge])
    assert resp.nodes[0].id == "c_1"
    assert resp.edges[0].type == "related"


def test_review_queue_resolve_request_rejects_invalid_action():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReviewQueueResolveRequest(action="delete")


def test_highlight_process_result_defaults():
    h = Highlight(id="h_1", source_quote="q", source_title="T", created_at="2026-07-30T00:00:00Z")
    result = HighlightProcessResult(highlight=h)
    assert result.concepts == []
    assert result.edges == []
    assert result.queued == []
    assert result.extraction_error is None
