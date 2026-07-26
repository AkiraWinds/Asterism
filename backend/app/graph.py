"""Top-level system graph (Task 8): wraps the Task 7 analysis subgraph as a
single "analyze" node inside a checkpointed StateGraph over SystemState. The
checkpointer lets a retry resume from the last saved SystemState for a given
thread_id (source_id) instead of starting from scratch.
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.analysis.graph import build_analysis_graph
from app.analysis.state import AnalysisState
from app.state import SystemState

_analysis_subgraph = build_analysis_graph()


def _analyze_node(state: SystemState) -> dict:
    analysis_input: AnalysisState = {
        "source_id": state["source_id"],
        "title": state["title"],
        "content": state["content"],
        "source_url": state.get("source_url"),
        "data_root": state["data_root"],
        "config": state["config"],
    }

    # Copy any previously-succeeded fields from the existing partial result
    # into the fresh analysis_input. The analysis subgraph's nodes (Task 7)
    # skip recomputation for fields that already have a value, so seeding
    # analysis_input with the prior result is what makes a retry only
    # recompute the fields that failed (those still None with an *_error set).
    existing = state.get("result")
    if existing is not None:
        analysis_input["triage"] = existing.triage
        analysis_input["triage_error"] = existing.triage_error
        analysis_input["digest"] = existing.digest
        analysis_input["digest_error"] = existing.digest_error
        analysis_input["critique"] = existing.critique
        analysis_input["critique_error"] = existing.critique_error
        analysis_input["claims"] = existing.claims
        analysis_input["claims_error"] = existing.claims_error
        analysis_input["connections"] = existing.connections

    output = _analysis_subgraph.invoke(analysis_input)
    return {"result": output["result"]}


def build_system_graph(checkpointer):
    builder = StateGraph(SystemState)
    builder.add_node("analyze", _analyze_node)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    return builder.compile(checkpointer=checkpointer)


def checkpoint_db_path(data_root: Path) -> Path:
    cache_dir = data_root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "analysis_checkpoints.db"
