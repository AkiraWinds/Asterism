# backend/tests/test_graph_schema.py
from app.schemas.graph import ConceptNode, Edge, GraphResponse, HighlightProcessResult, ReviewQueueEntry, ReviewQueueResolveRequest, GraphNode, GraphEdge
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
    node = GraphNode(id="c_1", kind="concept", term="RAG", definition="def")
    edge = GraphEdge(id="e_1", from_id="c_1", to_id="c_2", kind="concept_relation", type="related", summary="s")
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


def test_graph_node_accepts_concept_fields():
    node = GraphNode(id="c_1", kind="concept", term="RAG", definition="def", self_relevant=True, golden=True)
    assert node.kind == "concept"
    assert node.definition == "def"
    assert node.is_aspect is False


def test_graph_node_defaults_for_non_concept_kinds():
    node = GraphNode(id="src_1", kind="source", term="Some Article")
    assert node.definition is None
    assert node.self_relevant is False
    assert node.golden is False


def test_graph_edge_type_optional_for_structural_edges():
    edge = GraphEdge(id="e_1", from_id="c_1", to_id="src_1", kind="source_link")
    assert edge.type is None
    assert edge.summary == ""
