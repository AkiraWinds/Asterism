import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SourceRecord:
    id: str
    title: str
    created_at: str
    content: str


def create_source(data_root: Path, title: str, content: str) -> SourceRecord:
    source_id = uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).isoformat()
    source_dir = data_root / "library" / source_id
    source_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": source_id,
        "created_at": created_at,
        "type": "text",
        "original_title": title,
    }
    (source_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    (source_dir / "content.md").write_text(f'---\ntitle: "{title}"\n---\n\n{content}\n')

    return SourceRecord(id=source_id, title=title, created_at=created_at, content=content)


def list_sources(data_root: Path) -> list[SourceRecord]:
    library_dir = data_root / "library"
    if not library_dir.exists():
        return []

    records = []
    for source_dir in library_dir.iterdir():
        meta_path = source_dir / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        records.append(
            SourceRecord(
                id=meta["id"],
                title=meta["original_title"],
                created_at=meta["created_at"],
                content="",
            )
        )
    records.sort(key=lambda r: r.created_at, reverse=True)
    return records


def get_source(data_root: Path, source_id: str) -> SourceRecord | None:
    source_dir = data_root / "library" / source_id
    meta_path = source_dir / "meta.json"
    content_path = source_dir / "content.md"
    if not meta_path.exists() or not content_path.exists():
        return None

    meta = json.loads(meta_path.read_text())
    raw = content_path.read_text()
    body = raw.split("---", 2)[-1].lstrip("\n") if raw.startswith("---") else raw

    return SourceRecord(
        id=meta["id"],
        title=meta["original_title"],
        created_at=meta["created_at"],
        content=body,
    )
