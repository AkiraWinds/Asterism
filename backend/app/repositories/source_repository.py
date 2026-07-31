"""Source CRUD and analysis read/write operations for the library."""

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.analysis import AnalysisResult
from app.schemas.chat import ChatHistory, ChatTurn
from app.schemas.feedback import FeedbackEntry, FeedbackHistory
from app.schemas.highlight import Highlight, HighlightHistory


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
    (source_dir / "content.md").write_text(f'---\ntitle: {json.dumps(title)}\n---\n\n{content}\n')

    return SourceRecord(id=source_id, title=title, created_at=created_at, content=content)


def create_source_from_url(
    data_root: Path, url: str, title: str, html: str, content: str
) -> SourceRecord:
    source_id = uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).isoformat()
    source_dir = data_root / "library" / source_id
    source_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": source_id,
        "created_at": created_at,
        "type": "html",
        "original_title": title,
        "source_url": url,
        "original_file": "original.html",
    }
    try:
        (source_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        (source_dir / "original.html").write_text(html)
        (source_dir / "content.md").write_text(f'---\ntitle: {json.dumps(title)}\n---\n\n{content}\n')
    except OSError as exc:
        # A partial write (e.g. disk full mid-sequence) must not leave a directory
        # that only has meta.json — per the file-existence status model that reads
        # as "Processing" forever with no way to surface the failure.
        try:
            (source_dir / "error.txt").write_text(f"Failed to write source files: {exc}")
        except OSError:
            shutil.rmtree(source_dir, ignore_errors=True)
        raise

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
    library_dir = data_root / "library"
    source_dir = library_dir / source_id

    resolved_source_dir = source_dir.resolve()
    resolved_library_dir = library_dir.resolve()
    if not resolved_source_dir.is_relative_to(resolved_library_dir):
        return None

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


def write_analysis(data_root: Path, source_id: str, result: AnalysisResult) -> None:
    """Write an AnalysisResult to analysis.json in the source directory."""
    source_dir = data_root / "library" / source_id
    (source_dir / "analysis.json").write_text(result.model_dump_json(indent=2))


def read_analysis(data_root: Path, source_id: str) -> AnalysisResult | None:
    """Read and parse analysis.json if it exists, else return None."""
    analysis_path = data_root / "library" / source_id / "analysis.json"
    if not analysis_path.exists():
        return None
    return AnalysisResult.model_validate_json(analysis_path.read_text())


def list_analysis_summaries(data_root: Path, exclude_id: str) -> list[dict]:
    """Return list of analyzed sources with their id, title, and digest summary.

    Filters to include only sources that have both meta.json and analysis.json,
    and excludes the source with ID matching exclude_id.
    """
    library_dir = data_root / "library"
    if not library_dir.exists():
        return []

    summaries = []
    for source_dir in library_dir.iterdir():
        if source_dir.name == exclude_id:
            continue
        meta_path = source_dir / "meta.json"
        analysis_path = source_dir / "analysis.json"
        if not meta_path.exists() or not analysis_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        analysis = AnalysisResult.model_validate_json(analysis_path.read_text())
        # Skip if no digest was analyzed
        if analysis.digest is None:
            continue
        summaries.append({"id": meta["id"], "title": meta["original_title"], "summary": analysis.digest.summary})
    return summaries


def list_analysis_claims(data_root: Path, source_ids: list[str]) -> list[dict]:
    """Return list of sources with claims for each ID in source_ids.

    For each requested source_id, includes it only if it has both meta.json and
    analysis.json with at least one claim. Returns dicts with id, title, and claims.
    """
    library_dir = data_root / "library"
    results = []
    for source_id in source_ids:
        source_dir = library_dir / source_id
        meta_path = source_dir / "meta.json"
        analysis_path = source_dir / "analysis.json"
        if not meta_path.exists() or not analysis_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        analysis = AnalysisResult.model_validate_json(analysis_path.read_text())
        # Skip sources with no claims
        if not analysis.claims:
            continue
        results.append({"id": meta["id"], "title": meta["original_title"], "claims": analysis.claims})
    return results


def append_chat_turn(data_root: Path, source_id: str, turn: ChatTurn) -> None:
    """Append one turn to chat.json, creating the file if it doesn't exist yet."""
    chat_path = data_root / "library" / source_id / "chat.json"
    history = read_chat(data_root, source_id)
    history.turns.append(turn)
    chat_path.write_text(history.model_dump_json(indent=2))


def read_chat(data_root: Path, source_id: str) -> ChatHistory:
    """Read chat.json if it exists, else return an empty ChatHistory."""
    chat_path = data_root / "library" / source_id / "chat.json"
    if not chat_path.exists():
        return ChatHistory()
    return ChatHistory.model_validate_json(chat_path.read_text())


def append_highlight(data_root: Path, source_id: str, highlight: Highlight) -> None:
    """Append one highlight to highlights.json, creating the file if it doesn't exist yet."""
    highlights_path = data_root / "library" / source_id / "highlights.json"
    history = read_highlights(data_root, source_id)
    history.highlights.append(highlight)
    highlights_path.write_text(history.model_dump_json(indent=2))


def find_duplicate_highlight(data_root: Path, source_id: str, source_quote: str, note: str | None) -> Highlight | None:
    """Return an existing highlight in this source with the same (source_quote, note)
    pair, or None. Exact match after stripping surrounding whitespace — catches the
    accidental double-submit case (same selection saved twice within seconds), not
    paraphrases or a deliberate re-highlight with a different note."""
    normalized_note = note.strip() if note else None
    for h in read_highlights(data_root, source_id).highlights:
        existing_note = h.note.strip() if h.note else None
        if h.source_quote.strip() == source_quote.strip() and existing_note == normalized_note:
            return h
    return None


def read_highlights(data_root: Path, source_id: str) -> HighlightHistory:
    """Read highlights.json if it exists, else return an empty HighlightHistory."""
    highlights_path = data_root / "library" / source_id / "highlights.json"
    if not highlights_path.exists():
        return HighlightHistory()
    return HighlightHistory.model_validate_json(highlights_path.read_text())


def read_source_url(data_root: Path, source_id: str) -> str | None:
    """Read meta.json's source_url field, present only for URL-ingested sources
    (see create_source_from_url) — None for pasted-text/write-text sources."""
    meta_path = data_root / "library" / source_id / "meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    return meta.get("source_url")


def update_highlight_note(data_root: Path, source_id: str, highlight_id: str, note: str | None) -> Highlight | None:
    """Update one highlight's note in place, returning the updated Highlight,
    or None if no highlight with that id exists. A single editable note field,
    not a growing list of comments (see design doc's Data Model section)."""
    history = read_highlights(data_root, source_id)
    for i, h in enumerate(history.highlights):
        if h.id == highlight_id:
            updated = h.model_copy(update={"note": note})
            history.highlights[i] = updated
            highlights_path = data_root / "library" / source_id / "highlights.json"
            highlights_path.write_text(history.model_dump_json(indent=2))
            return updated
    return None


def read_feedback(data_root: Path, source_id: str) -> FeedbackHistory:
    """Read feedback.json if it exists, else return an empty FeedbackHistory."""
    feedback_path = data_root / "library" / source_id / "feedback.json"
    if not feedback_path.exists():
        return FeedbackHistory()
    return FeedbackHistory.model_validate_json(feedback_path.read_text())


def _write_feedback(data_root: Path, source_id: str, history: FeedbackHistory) -> None:
    feedback_path = data_root / "library" / source_id / "feedback.json"
    feedback_path.write_text(history.model_dump_json(indent=2))


def find_feedback_entry(
    data_root: Path, source_id: str, kind: str, section: str | None, content: str
) -> FeedbackEntry | None:
    """Return the feedback entry matching (kind, section, content) exactly after
    whitespace-normalization, or None. Mirrors find_duplicate_highlight's matching
    rule — feedback is matched by content, not by analysis.json's reanalyze-volatile
    ids (see the design doc's Key Design Decision)."""
    normalized_content = content.strip()
    for entry in read_feedback(data_root, source_id).entries:
        if entry.kind == kind and entry.section == section and entry.content.strip() == normalized_content:
            return entry
    return None


def upsert_feedback(
    data_root: Path, source_id: str, kind: str, section: str | None, content: str,
    term: str | None, rating: str,
) -> FeedbackEntry:
    """Create a new feedback entry for (kind, section, content), or update the
    existing one's rating if it already exists. Returns the entry either way, so
    the caller always has its id."""
    history = read_feedback(data_root, source_id)
    existing = find_feedback_entry(data_root, source_id, kind, section, content)
    now = datetime.now(timezone.utc).isoformat()

    if existing is not None:
        for entry in history.entries:
            if entry.id == existing.id:
                entry.rating = rating
                entry.updated_at = now
                if term is not None:
                    entry.term = term
                _write_feedback(data_root, source_id, history)
                return entry

    entry = FeedbackEntry(
        id=f"fb_{uuid.uuid4().hex[:10]}", kind=kind, section=section, content=content,
        term=term, rating=rating, created_at=now, updated_at=now,
    )
    history.entries.append(entry)
    _write_feedback(data_root, source_id, history)
    return entry


def mark_feedback_promoted(data_root: Path, source_id: str, feedback_id: str) -> FeedbackEntry | None:
    """Set promoted=True/promoted_at on the given feedback entry. Returns the
    updated entry, or None if feedback_id doesn't exist."""
    history = read_feedback(data_root, source_id)
    for entry in history.entries:
        if entry.id == feedback_id:
            entry.promoted = True
            entry.promoted_at = datetime.now(timezone.utc).isoformat()
            _write_feedback(data_root, source_id, history)
            return entry
    return None
