from app.schemas.highlight import Highlight, HighlightCreateRequest, HighlightHistory, HighlightUpdateRequest


def test_highlight_defaults_note_and_source_url_to_none():
    h = Highlight(id="h_1", source_quote="quoted text", source_title="Some Article", created_at="2026-07-30T00:00:00Z")
    assert h.note is None
    assert h.source_url is None


def test_highlight_history_defaults_to_empty_list():
    assert HighlightHistory().highlights == []


def test_highlight_create_request_accepts_optional_note():
    req = HighlightCreateRequest(source_quote="quoted text")
    assert req.note is None
    req_with_note = HighlightCreateRequest(source_quote="quoted text", note="my note")
    assert req_with_note.note == "my note"


def test_highlight_update_request_accepts_null_note():
    req = HighlightUpdateRequest(note=None)
    assert req.note is None
