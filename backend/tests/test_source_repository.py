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
