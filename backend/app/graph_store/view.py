"""Builds the heterogeneous GET /graph response (concept, source, and wiki
nodes/edges) by combining the existing concept-graph store with the
already-built wiki/source readers. Computes everything on read — no new
rows are ever written to graph.db. See
docs/superpowers/specs/2026-09-10-graph-multi-entity-view-design.md.
"""

from pathlib import Path

from app.graph_store.store import list_concepts, list_edges
from app.repositories.source_repository import list_sources
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse
from app.wiki.store_reader import get_concept_provenance


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

    # Source nodes/edges: concept -> source provenance (concept_highlights
    # union concept_sources, via get_concept_provenance), deduped so a
    # source referenced by several concepts appears as one node.
    source_title_by_id = {r.id: r.title for r in list_sources(data_root)}
    seen_source_ids: set[str] = set()
    for concept in concepts:
        provenance = get_concept_provenance(db_path, concept["id"])
        linked_source_ids = {entry["source_id"] for entry in provenance}
        for source_id in linked_source_ids:
            title = source_title_by_id.get(source_id)
            if title is None:
                continue  # source was deleted after this concept was extracted from it
            if source_id not in seen_source_ids:
                seen_source_ids.add(source_id)
                nodes.append(GraphNode(id=f"src_{source_id}", kind="source", term=title))
            edges.append(GraphEdge(
                id=f"srclink_{concept['id']}_{source_id}", from_id=concept["id"], to_id=f"src_{source_id}",
                kind="source_link",
            ))

    return GraphResponse(nodes=nodes, edges=edges)
