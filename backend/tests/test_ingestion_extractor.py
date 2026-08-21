from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ingestion.extractor import extract_content


def _rich_article_html() -> str:
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    return f"<html><head><title>Rich Article</title></head><body><article><h1>A Real Article Title</h1><p>{paragraph}</p></article></body></html>"


def _rich_article_html_with_link() -> str:
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    linked_sentence = 'As reported by <a href="https://example.com/source">the source</a>, this happened.'
    return f"<html><head><title>Rich Article</title></head><body><article><h1>A Real Article Title</h1><p>{linked_sentence} {paragraph}</p></article></body></html>"


def _thin_html() -> str:
    return "<html><head><title>Thin</title></head><body><p>Hi</p></body></html>"


def _article_with_table_dropped_by_trafilatura() -> str:
    # trafilatura discards any element whose class matches its generic "embed" boilerplate
    # regex, including CMS wrapper classes like Webflow's `w-embed` that aren't boilerplate.
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    table = (
        '<div class="w-embed"><table><thead><tr><th>Timing</th><th>What</th></tr></thead>'
        "<tbody><tr><td>Offline</td><td>desc</td></tr></tbody></table></div>"
    )
    return (
        f"<html><head><title>Rich Article</title></head><body><article><h1>A Real Article Title</h1>"
        f"<p>{paragraph}</p>{table}<p>{paragraph}</p></article></body></html>"
    )


def _article_with_svg_diagram_dropped_by_trafilatura() -> str:
    # trafilatura's image allowlist only matches raster formats, so an <img src="*.svg"> is
    # never extracted even though the surrounding prose is.
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    figure = '<figure><img alt="diagram" src="https://example.com/diagram.svg"/></figure>'
    return (
        f"<html><head><title>Rich Article</title></head><body><article><h1>A Real Article Title</h1>"
        f"<p>{paragraph}</p>{figure}<p>{paragraph}</p></article></body></html>"
    )


def test_extract_content_uses_trafilatura_when_extraction_is_long_enough(tmp_path: Path):
    with patch("app.ingestion.extractor.build_provider") as mock_build_provider:
        result = extract_content(_rich_article_html(), "https://example.com/rich", tmp_path)

    assert "A Real Article Title" in result
    assert len(result) > 500
    mock_build_provider.assert_not_called()


def test_extract_content_preserves_inline_links(tmp_path: Path):
    with patch("app.ingestion.extractor.build_provider") as mock_build_provider:
        result = extract_content(_rich_article_html_with_link(), "https://example.com/rich", tmp_path)

    assert "[the source](https://example.com/source)" in result
    mock_build_provider.assert_not_called()


def test_extract_content_falls_back_to_ai_when_trafilatura_extraction_is_short(tmp_path: Path):
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "# Thin\n\nAI-extracted content."

    with patch("app.ingestion.extractor.load_config", return_value="fake-config") as mock_load_config, \
         patch("app.ingestion.extractor.build_provider", return_value=fake_provider) as mock_build_provider:
        result = extract_content(_thin_html(), "https://example.com/thin", tmp_path)

    assert result == "# Thin\n\nAI-extracted content."
    mock_load_config.assert_called_once_with(tmp_path)
    mock_build_provider.assert_called_once_with("fake-config", tmp_path)
    fake_provider.complete.assert_called_once()
    prompt = fake_provider.complete.call_args[0][0]
    assert "Thin" in prompt


def test_extract_content_falls_back_to_ai_when_trafilatura_drops_a_table(tmp_path: Path):
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "# Rich\n\n| Timing | What |\n|---|---|\n| Offline | desc |"

    with patch("app.ingestion.extractor.load_config", return_value="fake-config"), \
         patch("app.ingestion.extractor.build_provider", return_value=fake_provider) as mock_build_provider:
        result = extract_content(_article_with_table_dropped_by_trafilatura(), "https://example.com/rich", tmp_path)

    assert result == fake_provider.complete.return_value
    mock_build_provider.assert_called_once()


def test_extract_content_falls_back_to_ai_when_trafilatura_drops_an_svg_diagram(tmp_path: Path):
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "# Rich\n\n![diagram](https://example.com/diagram.svg)"

    with patch("app.ingestion.extractor.load_config", return_value="fake-config"), \
         patch("app.ingestion.extractor.build_provider", return_value=fake_provider) as mock_build_provider:
        result = extract_content(
            _article_with_svg_diagram_dropped_by_trafilatura(), "https://example.com/rich", tmp_path
        )

    assert result == fake_provider.complete.return_value
    mock_build_provider.assert_called_once()
