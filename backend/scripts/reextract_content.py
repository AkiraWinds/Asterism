"""Backfill content.md for existing HTML sources from their immutable original.html.

Needed after any fix to app.ingestion.extract_content (e.g. the 2026-08-21 fix for
trafilatura silently dropping tables/SVG diagrams): content.md was written once at
capture time and is never touched again on its own, so already-captured sources keep
the old, possibly-incomplete extraction until something re-runs extract_content and
overwrites content.md. Per CLAUDE.md's file-system architecture, original.html is
immutable and content.md is derived/regenerable, so this is a safe, one-directional
rewrite — it never touches meta.json or original.html.

This only re-extracts content.md. It does NOT re-run analysis (digest/critique/claims),
since that's a separate, costlier step (LLM calls) that isn't always needed just because
the raw content changed. Re-run analysis per source afterward (POST /sources/{id}/analyze,
or "Analyze"/"Reanalyze" in the UI) for sources where you also want the digest/concepts
refreshed against the corrected content.

Usage: uv run python scripts/reextract_content.py [--dry-run] [source_id ...]
  --dry-run: report which sources would change without writing anything.
  source_id: limit to specific source ids (default: every HTML source in the library).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_data_root  # noqa: E402
from app.ingestion.extractor import extract_content  # noqa: E402
from app.repositories.source_repository import list_sources  # noqa: E402


def _content_body(content_md: str) -> str:
    """Strip the '---\\ntitle: ...\\n---\\n\\n' frontmatter this repo prepends to content.md."""
    if content_md.startswith("---"):
        end = content_md.find("---", 3)
        if end != -1:
            return content_md[end + 3 :].lstrip("\n")
    return content_md


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    only_ids = {a for a in args if a != "--dry-run"}

    data_root = get_data_root()
    changed = 0
    skipped = 0

    for record in list_sources(data_root):
        if only_ids and record.id not in only_ids:
            continue

        source_dir = data_root / "library" / record.id
        html_path = source_dir / "original.html"
        if not html_path.exists():
            continue  # text-pasted sources have no original.html to re-extract from

        meta = json.loads((source_dir / "meta.json").read_text())
        url = meta.get("source_url", "")
        html = html_path.read_text(encoding="utf-8")

        new_extracted = extract_content(html, url, data_root)
        old_body = _content_body(record.content)

        if new_extracted.strip() == old_body.strip():
            skipped += 1
            continue

        changed += 1
        print(f"{'[dry-run] would update' if dry_run else 'updating'}: {record.id} — {record.title}")
        if not dry_run:
            content_path = source_dir / "content.md"
            content_path.write_text(
                f'---\ntitle: {json.dumps(record.title)}\n---\n\n{new_extracted}\n',
                encoding="utf-8",
            )

    print(f"\n{changed} changed, {skipped} unchanged" + (" (dry run, nothing written)" if dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
