"""CLI entry point for a wiki compile run, meant to be invoked by an
external scheduler (cron/launchd) — this repo has no in-process scheduler
by design. See docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md.

Usage: python scripts/wiki_compile.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_data_root  # noqa: E402
from app.providers.factory import build_provider  # noqa: E402
from app.repositories.config_repository import ConfigError, load_config  # noqa: E402
from app.wiki.compile import run_compile  # noqa: E402


def main() -> int:
    data_root = get_data_root()
    try:
        config = load_config(data_root)
    except ConfigError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    provider = build_provider(config, data_root)
    result = run_compile(data_root, provider)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
