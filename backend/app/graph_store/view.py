"""Builds the heterogeneous GET /graph response (concept, source, and wiki
nodes/edges) by combining the existing concept-graph store with the
already-built wiki/source readers. Computes everything on read — no new
rows are ever written to graph.db. See
docs/superpowers/specs/2026-09-10-graph-multi-entity-view-design.md.
"""

from pathlib import Path

from app.graph_store.store import list_concepts, list_edges
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse


def build_graph_response(data_root: Path, db_path: Path) -> GraphResponse:
    concepts = list_concepts(db_path)
    concept_ids = {c["id"] for c in concepts}

    nodes: list[GraphNode] = [
        GraphNode(
            id=c["id"], kind="concept", term=c["term"], definition=c["definition"],
            self_relevant=bool(c["self_relevant"]), golden=bool(c["golden"]),
        )
        for c in concepts
    ]
    # Defensive filter (pre-existing behavior, relocated from routers/graph.py):
    # only return edges whose endpoints both still exist as nodes.
    edges: list[GraphEdge] = [
        GraphEdge(id=e["id"], from_id=e["from_id"], to_id=e["to_id"], kind="concept_relation",
                   type=e["type"], summary=e["summary"])
        for e in list_edges(db_path)
        if e["from_id"] in concept_ids and e["to_id"] in concept_ids
    ]

    return GraphResponse(nodes=nodes, edges=edges)
