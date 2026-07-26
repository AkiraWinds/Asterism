"""Domain-local LangGraph graph that fans out to the 4 parallel analysis nodes
(triage, digest, critique, claims), then fans in to find_connections and finalize.

There is no separate "merge" node: each of the 4 parallel nodes writes to a
distinct key in AnalysisState (triage/digest/critique/claims), so there is
nothing to reconcile between them. LangGraph itself merges their partial
state-dict returns into the shared state as they complete, which makes
find_connections the natural fan-in point once all four have written their
keys.
"""

from langgraph.graph import END, START, StateGraph

from app.analysis.connections import find_connections, finalize
from app.analysis.nodes import run_claims, run_critique, run_digest, run_triage
from app.analysis.state import AnalysisState
from app.schemas.analysis import AnalysisResult


class _GraphState(AnalysisState):
    """AnalysisState plus the `result` key that `finalize` produces.

    LangGraph only propagates state keys declared on the schema passed to
    StateGraph, so `result` has to be declared somewhere for finalize's
    `{"result": ...}` return to survive into `.invoke()`'s output. It's added
    here rather than in AnalysisState itself (Task 4, not to be modified)
    since `result` is an output of this graph, not an input any node reads.
    """

    result: AnalysisResult


def build_analysis_graph():
    builder = StateGraph(_GraphState)

    builder.add_node("triage", run_triage)
    builder.add_node("digest", run_digest)
    builder.add_node("critique", run_critique)
    builder.add_node("claims", run_claims)
    builder.add_node("find_connections", find_connections)
    builder.add_node("finalize", finalize)

    # Fan out: all 4 analysis nodes run in parallel from START.
    builder.add_edge(START, "triage")
    builder.add_edge(START, "digest")
    builder.add_edge(START, "critique")
    builder.add_edge(START, "claims")

    # Fan in: find_connections waits on all 4 parallel nodes (LangGraph runs
    # a node only once every incoming edge's source has completed).
    builder.add_edge("triage", "find_connections")
    builder.add_edge("digest", "find_connections")
    builder.add_edge("critique", "find_connections")
    builder.add_edge("claims", "find_connections")

    builder.add_edge("find_connections", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()
