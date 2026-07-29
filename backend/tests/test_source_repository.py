import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.repositories.source_repository import (
    create_source,
    get_source,
    list_sources,
    list_analysis_claims,
    list_analysis_summaries,
    read_analysis,
    write_analysis,
    append_chat_turn,
    read_chat,
)
from app.schemas.analysis import AnalysisResult, Claim, Digest
from app.schemas.chat import ChatHistory, ChatTurn


def test_create_source_writes_meta_and_content(tmp_path: Path):
    record = create_source(tmp_path, title="My First Note", content="Hello world")

    source_dir = tmp_path / "library" / record.id
    assert (source_dir / "meta.json").exists()
    assert (source_dir / "content.md").exists()
    assert record.title == "My First Note"


def test_list_sources_returns_created_sources(tmp_path: Path):
    create_source(tmp_path, title="First", content="one")
    create_source(tmp_path, title="Second", content="two")

    records = list_sources(tmp_path)

    assert len(records) == 2
    assert {r.title for r in records} == {"First", "Second"}


def test_list_sources_empty_when_no_library(tmp_path: Path):
    assert list_sources(tmp_path) == []


def test_get_source_returns_full_content(tmp_path: Path):
    created = create_source(tmp_path, title="Note", content="Body text here")

    fetched = get_source(tmp_path, created.id)

    assert fetched is not None
    assert fetched.title == "Note"
    assert "Body text here" in fetched.content


def test_get_source_returns_none_when_missing(tmp_path: Path):
    assert get_source(tmp_path, "does-not-exist") is None


def test_get_source_rejects_path_traversal(tmp_path: Path):
    # A source_id containing traversal segments must not escape data_root/library
    (tmp_path / "library").mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "meta.json").write_text(
        '{"id": "x", "created_at": "now", "type": "text", "original_title": "Secret"}'
    )
    (outside_dir / "content.md").write_text("secret content")

    result = get_source(tmp_path, "../outside")

    assert result is None


def test_create_source_from_url_writes_meta_with_url_fields(tmp_path: Path):
    from app.repositories.source_repository import create_source_from_url

    record = create_source_from_url(
        tmp_path,
        url="https://example.com/article",
        title="Example Article",
        html="<html><body>raw html</body></html>",
        content="Extracted markdown body",
    )

    source_dir = tmp_path / "library" / record.id
    meta = json.loads((source_dir / "meta.json").read_text())
    assert meta["type"] == "html"
    assert meta["source_url"] == "https://example.com/article"
    assert meta["original_file"] == "original.html"
    assert meta["original_title"] == "Example Article"

    assert (source_dir / "original.html").read_text() == "<html><body>raw html</body></html>"
    assert record.title == "Example Article"
    assert record.content == "Extracted markdown body"


def test_create_source_from_url_writes_error_txt_on_partial_write_failure(tmp_path: Path):
    from app.repositories.source_repository import create_source_from_url

    original_write_text = Path.write_text
    call_count = {"n": 0}

    def flaky_write_text(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:  # fail on original.html, after meta.json succeeded
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)

    with patch.object(Path, "write_text", flaky_write_text):
        with pytest.raises(OSError):
            create_source_from_url(
                tmp_path,
                url="https://example.com/article",
                title="Example Article",
                html="<html>raw</html>",
                content="Extracted markdown body",
            )

    source_dirs = list((tmp_path / "library").iterdir())
    assert len(source_dirs) == 1
    source_dir = source_dirs[0]
    assert (source_dir / "meta.json").exists()
    assert (source_dir / "error.txt").exists()
    assert "disk full" in (source_dir / "error.txt").read_text()


def test_create_source_from_url_is_retrievable_via_get_source(tmp_path: Path):
    from app.repositories.source_repository import create_source_from_url, get_source

    created = create_source_from_url(
        tmp_path,
        url="https://example.com/article",
        title="Example Article",
        html="<html><body>raw html</body></html>",
        content="Extracted markdown body",
    )

    fetched = get_source(tmp_path, created.id)

    assert fetched is not None
    assert fetched.title == "Example Article"
    assert "Extracted markdown body" in fetched.content


def test_write_then_read_analysis(tmp_path: Path):
    record = create_source(tmp_path, title="Test", content="Body")
    result = AnalysisResult(
        digest=Digest(summary="A summary."),
        connections=[],
        analyzed_at="2026-07-26T12:00:00+00:00",
    )

    write_analysis(tmp_path, record.id, result)
    loaded = read_analysis(tmp_path, record.id)

    assert loaded is not None
    assert loaded.digest.summary == "A summary."


def test_read_analysis_returns_none_when_missing(tmp_path: Path):
    record = create_source(tmp_path, title="Test", content="Body")
    assert read_analysis(tmp_path, record.id) is None


def test_list_analysis_summaries_excludes_given_id_and_unanalyzed_sources(tmp_path: Path):
    analyzed = create_source(tmp_path, title="Analyzed", content="Body")
    unanalyzed = create_source(tmp_path, title="Unanalyzed", content="Body")
    write_analysis(
        tmp_path,
        analyzed.id,
        AnalysisResult(digest=Digest(summary="Summary of analyzed."), analyzed_at="2026-07-26T12:00:00+00:00"),
    )

    summaries = list_analysis_summaries(tmp_path, exclude_id="does-not-matter")

    ids = {s["id"] for s in summaries}
    assert analyzed.id in ids
    assert unanalyzed.id not in ids

    summaries_excluding_analyzed = list_analysis_summaries(tmp_path, exclude_id=analyzed.id)
    assert analyzed.id not in {s["id"] for s in summaries_excluding_analyzed}


def test_list_analysis_claims_returns_only_requested_ids_with_claims(tmp_path: Path):
    source = create_source(tmp_path, title="Has Claims", content="Body")
    write_analysis(
        tmp_path,
        source.id,
        AnalysisResult(
            claims=[Claim(id="claim1", text="X is true", type="factual", source_quote="X")],
            analyzed_at="2026-07-26T12:00:00+00:00",
        ),
    )

    results = list_analysis_claims(tmp_path, [source.id, "nonexistent-id"])

    assert len(results) == 1
    assert results[0]["id"] == source.id
    assert results[0]["claims"][0].text == "X is true"


def test_read_chat_returns_empty_history_when_no_file(tmp_path: Path):
    source_id = create_source(tmp_path, title="T", content="c").id

    history = read_chat(tmp_path, source_id)

    assert history == ChatHistory(turns=[])


def test_append_chat_turn_creates_and_appends(tmp_path: Path):
    source_id = create_source(tmp_path, title="T", content="c").id

    append_chat_turn(
        tmp_path, source_id, ChatTurn(role="user", content="hi", created_at="2026-07-29T12:00:00Z")
    )
    append_chat_turn(
        tmp_path, source_id, ChatTurn(role="assistant", content="hello back", created_at="2026-07-29T12:00:01Z")
    )

    history = read_chat(tmp_path, source_id)
    assert [t.role for t in history.turns] == ["user", "assistant"]
    assert history.turns[1].content == "hello back"
