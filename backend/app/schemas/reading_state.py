"""Pydantic model for reading_state.json: the file-existence-inferred marker
that a source has been read. Absence of the file means unread — same pattern
as the other file-based derived state in this repo (see CLAUDE.md's
"Processing Status (File-based)" section). Written once, on first read, and
never rewritten after — see mark_source_read in source_repository.py.
"""

from pydantic import BaseModel


class ReadingState(BaseModel):
    read_at: str
