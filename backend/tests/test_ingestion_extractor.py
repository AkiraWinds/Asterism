from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ingestion.extractor import extract_content


def _rich_article_html() -> str:
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    return f"<html><head><title>Rich Article</title></head><body><article><h1>A Real Article Title</h1><p>{paragraph}</p></article></body></html>"


def _thin_html() -> str:
    return "<html><head><title>Thin</title></head><body><p>Hi</p></body></html>"


def test_extract_content_uses_trafilatura_when_extraction_is_long_enough(tmp_path: Path):
    with patch("app.ingestion.extractor.build_provider") as mock_build_provider:
        result = extract_content(_rich_article_html(), "https://example.com/rich", tmp_path)

    assert "A Real Article Title" in result
    assert len(result) > 500
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
