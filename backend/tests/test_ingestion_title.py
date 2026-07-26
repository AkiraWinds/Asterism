import pytest
from app.ingestion.title import extract_title


class TestExtractOGTitle:
    """Test OG title extraction with various attribute orders and quote types."""

    def test_og_title_standard_order(self):
        """Test standard og:title extraction with property before content."""
        html = '<meta property="og:title" content="The OG Title">'
        title = extract_title(html, "https://example.com")
        assert title == "The OG Title"

    def test_og_title_reversed_attribute_order(self):
        """Test og:title extraction with content before property attribute."""
        html = '<meta content="The OG Title" property="og:title">'
        title = extract_title(html, "https://example.com")
        assert title == "The OG Title"

    def test_og_title_with_single_quotes(self):
        """Test og:title extraction with single quotes."""
        html = "<meta property='og:title' content='Single Quote Title'>"
        title = extract_title(html, "https://example.com")
        assert title == "Single Quote Title"

    def test_og_title_with_mixed_attributes(self):
        """Test og:title with other attributes interspersed."""
        html = '<meta property="og:title" name="something" content="Mixed Attributes Title">'
        title = extract_title(html, "https://example.com")
        assert title == "Mixed Attributes Title"

    def test_og_title_mismatched_quotes_double_to_single(self):
        """Test that mismatched quotes (opening double, closing single) don't match."""
        html = '<meta property="og:title" content="Mismatched Title\'>'
        title = extract_title(html, "https://example.com/page")
        # Should NOT extract the mismatched content, should fall back to hostname
        assert title == "example.com"

    def test_og_title_mismatched_quotes_single_to_double(self):
        """Test that mismatched quotes (opening single, closing double) don't match."""
        html = "<meta property='og:title' content='Mismatched Title\">"
        title = extract_title(html, "https://example.com/page")
        # Should NOT extract the mismatched content, should fall back to hostname
        assert title == "example.com"

    def test_og_title_with_whitespace_around_equals(self):
        """Test og:title extraction with extra whitespace around = signs."""
        html = '<meta property = "og:title" content = "Whitespace Title">'
        title = extract_title(html, "https://example.com")
        assert title == "Whitespace Title"

    def test_og_title_case_insensitive(self):
        """Test that og:title matching is case-insensitive."""
        html = '<meta PROPERTY="og:title" CONTENT="Case Insensitive Title">'
        title = extract_title(html, "https://example.com")
        assert title == "Case Insensitive Title"

    def test_og_title_with_extra_whitespace_in_value(self):
        """Test that title values preserve content but strip outer whitespace."""
        html = '<meta property="og:title" content="  Whitespace Title  ">'
        title = extract_title(html, "https://example.com")
        assert title == "Whitespace Title"

    def test_og_title_empty_string(self):
        """Test og:title with empty content value."""
        html = '<meta property="og:title" content="">'
        title = extract_title(html, "https://example.com")
        # Empty string should not be used, falls back to title tag or hostname
        assert title == "example.com"

    def test_fallback_to_title_tag(self):
        """Test fallback to <title> tag when og:title not present."""
        html = "<title>Page Title</title>"
        title = extract_title(html, "https://example.com")
        assert title == "Page Title"

    def test_og_title_takes_precedence_over_title_tag(self):
        """Test that og:title is preferred over <title> tag."""
        html = '<meta property="og:title" content="OG Title"><title>Page Title</title>'
        title = extract_title(html, "https://example.com")
        assert title == "OG Title"

    def test_whitespace_only_title_tag_falls_back_to_hostname(self):
        """Test that a whitespace-only <title> doesn't win over the hostname fallback."""
        html = "<title>   </title>"
        title = extract_title(html, "https://example.com/some/path")
        assert title == "example.com"

    def test_fallback_to_hostname(self):
        """Test fallback to hostname when no og:title or title tag present."""
        html = "<p>Some content</p>"
        title = extract_title(html, "https://example.com/some/path")
        assert title == "example.com"

    def test_fallback_to_url_when_no_hostname(self):
        """Test fallback to full URL when hostname extraction fails."""
        html = "<p>Some content</p>"
        url = "file:///local/path"
        title = extract_title(html, url)
        assert title == url

    def test_multiple_og_title_tags_uses_first(self):
        """Test that only the first og:title is extracted."""
        html = (
            '<meta property="og:title" content="First OG Title">'
            '<meta property="og:title" content="Second OG Title">'
        )
        title = extract_title(html, "https://example.com")
        assert title == "First OG Title"

    def test_og_title_tag_similar_to_og_description(self):
        """Test that og:title doesn't match similar og: properties."""
        html = (
            '<meta property="og:description" content="Description">'
            '<meta property="og:title" content="Correct Title">'
        )
        title = extract_title(html, "https://example.com")
        assert title == "Correct Title"

    def test_real_world_html_example(self):
        """Test with realistic HTML structure."""
        html = """
        <html>
        <head>
            <meta charset="utf-8">
            <meta property="og:title" content="Real World Title">
            <meta content="Real World Description" property="og:description">
            <title>Fallback Title</title>
        </head>
        <body>Content</body>
        </html>
        """
        title = extract_title(html, "https://example.com")
        assert title == "Real World Title"
