from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.extractor import (
    ExtractionFailedError,
    _dropped_multiline_code,
    _resolve_relative_urls,
    extract_content,
)


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


def _article_with_decorative_header_svg_logo() -> str:
    # A header/nav logo <img src="*.svg"> sits *outside* <main>/<article>, ahead of the real
    # content in DOM order — the exact shape of docs sites like the OpenAI cookbook. It's
    # legitimately absent from trafilatura's markdown (it's chrome, not content) and must not
    # be mistaken for a dropped content image.
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    header = '<header><img alt="logo" src="https://example.com/logo.svg"/><nav>site nav</nav></header>'
    return (
        f"<html><head><title>Rich Article</title></head><body>{header}"
        f"<main><article><h1>A Real Article Title</h1><p>{paragraph}</p></article></main></body></html>"
    )


def test_extract_content_ignores_decorative_svg_outside_main_content(tmp_path: Path):
    with patch("app.ingestion.extractor.build_provider") as mock_build_provider:
        result = extract_content(_article_with_decorative_header_svg_logo(), "https://example.com/rich", tmp_path)

    assert "A Real Article Title" in result
    mock_build_provider.assert_not_called()


def _article_with_multiline_pre() -> str:
    # A Shiki/Prism-style syntax-highlighted code block: each line wrapped in its own
    # <span class="line">. Reproducing trafilatura's real flattening bug requires the scale
    # and complexity of an actual large docs page (verified live against the OpenAI cookbook
    # page that originally reported this) — a small isolated fixture like this one round-trips
    # through trafilatura correctly, so `_dropped_multiline_code` is unit-tested directly
    # against representative html/extracted strings instead of relying on trafilatura to
    # reproduce the collapse here (see `test_extract_content_falls_back_to_ai_when_trafilatura_flattens_a_code_block`
    # below for the integration path, which mocks trafilatura's return value instead).
    lines = "\n".join(f'<span class="line">line {i} of code here</span>' for i in range(1, 10))
    return f'<pre data-language="python"><code>{lines}</code></pre>'


def test_dropped_multiline_code_true_when_pre_collapses_to_single_line():
    html = f"<article>{_article_with_multiline_pre()}</article>"
    flattened = "line 1 of code here line 2 of code here line 3 of code here"
    assert _dropped_multiline_code(html, flattened) is True


def test_dropped_multiline_code_false_when_fenced_block_preserved():
    html = f"<article>{_article_with_multiline_pre()}</article>"
    fenced = "```\nline 1 of code here\nline 2 of code here\n```"
    assert _dropped_multiline_code(html, fenced) is False


def test_dropped_multiline_code_false_when_no_pre_present():
    assert _dropped_multiline_code("<article><p>No code here.</p></article>", "No code here.") is False


def test_extract_content_falls_back_to_ai_when_trafilatura_flattens_a_code_block(tmp_path: Path):
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "# Rich\n\n```\nline 1 of code here\nline 2 of code here\n```"
    paragraph = " ".join(f"This is sentence number {i} in a long article body." for i in range(1, 40))
    html = (
        f"<html><head><title>Rich Article</title></head><body><article><h1>A Real Article Title</h1>"
        f"<p>{paragraph}</p>{_article_with_multiline_pre()}<p>{paragraph}</p></article></body></html>"
    )
    # trafilatura's own real flattening only manifests at the scale/complexity of an actual
    # large docs page (see `_article_with_multiline_pre`'s docstring) — mocked here to exercise
    # extract_content's wiring to `_dropped_multiline_code` without needing that scale in a test.
    flattened = "A Real Article Title. " + paragraph + " line 1 of code here line 2 of code here " + paragraph

    with patch("app.ingestion.extractor.trafilatura.extract", return_value=flattened), \
         patch("app.ingestion.extractor.load_config", return_value="fake-config"), \
         patch("app.ingestion.extractor.build_provider", return_value=fake_provider) as mock_build_provider:
        result = extract_content(html, "https://example.com/rich", tmp_path)

    assert result == fake_provider.complete.return_value
    mock_build_provider.assert_called_once()


def test_resolve_relative_urls_resolves_image_and_link_targets():
    markdown = (
        "![Self-evolving loop](/cookbook/assets/images/baseline_agent.png)\n\n"
        "See the [docs](/cookbook/docs) for more, or the "
        "[external site](https://other.example.com/already-absolute)."
    )
    resolved = _resolve_relative_urls(markdown, "https://developers.openai.com/cookbook/examples/foo")

    assert "](https://developers.openai.com/cookbook/assets/images/baseline_agent.png)" in resolved
    assert "](https://developers.openai.com/cookbook/docs)" in resolved
    # Already-absolute URLs pass through unchanged (urljoin is a no-op on them).
    assert "](https://other.example.com/already-absolute)" in resolved


def test_extract_content_resolves_relative_image_urls_from_ai_fallback(tmp_path: Path):
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "# Rich\n\n![diagram](/assets/diagram.png)"

    with patch("app.ingestion.extractor.load_config", return_value="fake-config"), \
         patch("app.ingestion.extractor.build_provider", return_value=fake_provider):
        result = extract_content(_thin_html(), "https://example.com/some/page", tmp_path)

    assert result == "# Rich\n\n![diagram](https://example.com/assets/diagram.png)"


def test_extract_content_raises_when_ai_extractor_finds_no_content(tmp_path: Path):
    # A refusal like "I don't see an article body here..." reads exactly like any other
    # successful extraction (long prose) — only the sentinel the prompt asks for on purpose
    # lets us tell a real failure apart from real content and avoid persisting the refusal
    # text itself as the source's content.
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "NO_CONTENT_FOUND"

    with patch("app.ingestion.extractor.load_config", return_value="fake-config"), \
         patch("app.ingestion.extractor.build_provider", return_value=fake_provider):
        with pytest.raises(ExtractionFailedError):
            extract_content(_thin_html(), "https://example.com/thin", tmp_path)


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
