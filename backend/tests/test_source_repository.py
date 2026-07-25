import json
from pathlib import Path

from app.repositories.source_repository import create_source, get_source, list_sources


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
