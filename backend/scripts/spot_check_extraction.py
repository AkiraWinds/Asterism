"""Manual validation for the entity-extraction prompt rewrite (Task 7/8 of
docs/superpowers/plans/2026-08-01-entity-extraction-reference-lookup.md).
Not a pytest test and not run in CI — run by hand against your real
ASTERISM_DATA_ROOT, read the printed output, and judge whether the rewritten
prompts (few-shot, grounding, abstain) actually produce better concepts than
before, per the design doc's Validation section. Requires config.json to
have a working provider + embeddings_api_key already configured.

Usage: uv run python scripts/spot_check_extraction.py [N]
  N: how many real sources/highlights to sample (default 5 of each).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.concept_graph.prompts import build_extraction_prompt
from app.analysis.prompts import build_digest_prompt
from app.core.config import get_data_root
from app.providers.factory import build_provider
from app.repositories.config_repository import load_config
from app.repositories.source_repository import list_sources, read_highlights, read_source_url


def _read_content(data_root: Path, source_id: str) -> str | None:
    """Read source content from content.md, handling sources at any nested level.

    Looks first for a source at the top level (library/{source_id}/), then
    searches recursively in case the source is nested under a user-created folder.
    Returns None if no content.md found.
    """
    content_path = data_root / "library" / source_id / "content.md"
    if not content_path.exists():
        # Sources may live under a user-created folder, not top-level.
        matches = list(data_root.glob(f"library/**/{source_id}/content.md"))
        if not matches:
            return None
        content_path = matches[0]
    return content_path.read_text()


def main() -> None:
    """Spot-check extraction quality by sampling real sources and highlights.

    Tier-1: Sample N digest.concepts prompts from N sources' full content.
    Tier-2: Sample N highlights and show extraction results.

    Output is intentionally bare — printed prompts and LLM responses for manual
    inspection, not structured test assertions. Human judgment on specificity,
    grounding, and appropriate abstention is the acceptance criterion.
    """
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    data_root = get_data_root()
    config = load_config(data_root)
    provider = build_provider(config, data_root)

    sources = list_sources(data_root)[:n]

    print(f"=== Tier-1 (digest.concepts) spot check — {len(sources)} sources ===\n")
    for record in sources:
        content = _read_content(data_root, record.id)
        if content is None:
            continue
        prompt = build_digest_prompt(record.title, content[:4000])
        print(f"--- {record.title} ---")
        print(provider.complete(prompt))
        print()

    print(f"=== Tier-2 (highlight extraction) spot check ===\n")
    checked = 0
    for record in sources:
        history = read_highlights(data_root, record.id)
        for highlight in history.highlights:
            if checked >= n:
                break
            prompt = build_extraction_prompt(highlight.source_quote, highlight.note)
            print(f"--- highlight from {record.title}: \"{highlight.source_quote[:80]}...\" ---")
            print(provider.complete(prompt))
            print()
            checked += 1


if __name__ == "__main__":
    main()
