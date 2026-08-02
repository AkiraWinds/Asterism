"""CLI entry point for a Radar refresh run, meant to be invoked by an
external scheduler (cron/launchd) — this repo has no in-process scheduler
by design, matching scripts/wiki_compile.py. See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.

Usage: python scripts/radar_refresh.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_data_root  # noqa: E402
from app.providers.factory import build_provider  # noqa: E402
from app.radar.pipeline import refresh_radar  # noqa: E402
from app.repositories.config_repository import ConfigError, load_config, load_embeddings_api_key  # noqa: E402


def main() -> int:
    data_root = get_data_root()
    try:
        config = load_config(data_root)
        embeddings_api_key = load_embeddings_api_key(data_root)
    except ConfigError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    provider = build_provider(config, data_root)
    summary = refresh_radar(data_root, provider, embeddings_api_key)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
