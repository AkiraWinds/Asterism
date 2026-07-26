"""Top-level system state TypedDict for the system graph (Task 8). Mirrors
AnalysisState's input fields plus the final `result`, since the system graph
wraps the analysis subgraph as a single node rather than exposing its
per-field intermediate state.
"""

from pathlib import Path
from typing import TypedDict

from app.repositories.config_repository import AgentConfig
from app.schemas.analysis import AnalysisResult


class SystemState(TypedDict, total=False):
    source_id: str
    title: str
    content: str
    source_url: str | None
    data_root: Path
    config: AgentConfig
    result: AnalysisResult | None
