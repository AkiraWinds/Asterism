import pytest
from pydantic import ValidationError

from app.schemas.watchlist import WatchlistCreateRequest, WatchlistEntry, WatchlistHistory


def test_watchlist_entry_defaults():
    entry = WatchlistEntry(
        id="w_1", term="Agentic AI", status="pending",
        created_at="2026-08-01T00:00:00Z", updated_at="2026-08-01T00:00:00Z",
    )
    assert entry.draft_definition is None
    assert entry.resolved_concept_id is None


def test_watchlist_entry_rejects_invalid_status():
    with pytest.raises(ValidationError):
        WatchlistEntry(
            id="w_1", term="Agentic AI", status="not-a-status",
            created_at="2026-08-01T00:00:00Z", updated_at="2026-08-01T00:00:00Z",
        )


def test_watchlist_create_request_requires_term():
    with pytest.raises(ValidationError):
        WatchlistCreateRequest()


def test_watchlist_history_defaults_to_empty_list():
    assert WatchlistHistory().entries == []
