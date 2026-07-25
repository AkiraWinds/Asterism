from app.ingestion.title import extract_title


def test_extract_title_prefers_og_title():
    html = (
        '<html><head>'
        '<meta property="og:title" content="The OG Title">'
        '<title>The Title Tag</title>'
        '</head><body></body></html>'
    )
    assert extract_title(html, "https://example.com/a") == "The OG Title"


def test_extract_title_falls_back_to_title_tag():
    html = "<html><head><title>The Title Tag</title></head><body></body></html>"
    assert extract_title(html, "https://example.com/a") == "The Title Tag"


def test_extract_title_falls_back_to_hostname_when_neither_present():
    html = "<html><head></head><body>no title here</body></html>"
    assert extract_title(html, "https://example.com/a") == "example.com"
