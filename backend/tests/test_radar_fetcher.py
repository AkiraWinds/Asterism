import pytest

from app.radar.fetcher import FeedFetchError, fetch_feed_items

_SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
<channel>
  <title>Example Blog</title>
  <item>
    <title>Post One</title>
    <link>https://example.com/post-one</link>
    <description>A summary of post one.</description>
    <pubDate>Mon, 02 Aug 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Post Two</title>
    <link>https://example.com/post-two</link>
    <description>A summary of post two.</description>
  </item>
</channel>
</rss>
"""


def test_fetch_feed_items_parses_entries(monkeypatch):
    monkeypatch.setattr("app.radar.fetcher.fetch_url", lambda url: _SAMPLE_RSS)

    items = fetch_feed_items("https://example.com/rss.xml")

    assert len(items) == 2
    assert items[0]["url"] == "https://example.com/post-one"
    assert items[0]["title"] == "Post One"
    assert items[0]["summary"] == "A summary of post one."
    assert items[0]["published_at"] is not None
    assert items[1]["published_at"] is None  # no pubDate on the second item


def test_fetch_feed_items_raises_on_fetch_error(monkeypatch):
    from app.ingestion.fetcher import FetchError

    def _raise(url):
        raise FetchError("connection refused")

    monkeypatch.setattr("app.radar.fetcher.fetch_url", _raise)

    with pytest.raises(FeedFetchError):
        fetch_feed_items("https://example.com/rss.xml")


def test_fetch_feed_items_raises_on_unparseable_content(monkeypatch):
    monkeypatch.setattr("app.radar.fetcher.fetch_url", lambda url: "not xml at all, just plain text")

    with pytest.raises(FeedFetchError):
        fetch_feed_items("https://example.com/rss.xml")


def test_fetch_feed_items_does_not_let_feedparser_fetch_a_url_from_body(monkeypatch):
    # A malicious/misconfigured feed server could return a body that happens to
    # BE a URL (e.g. targeting cloud metadata endpoints). feedparser.parse()
    # would fetch that URL itself with zero SSRF protection if given a raw str,
    # bypassing fetch_url's guard entirely. Passing io.BytesIO forces feedparser
    # down its "already have data" path instead, so this must return no entries
    # (it's not valid feed XML) rather than silently fetching the URL-as-body.
    monkeypatch.setattr("app.radar.fetcher.fetch_url", lambda url: "http://169.254.169.254/latest/meta-data/")

    with pytest.raises(FeedFetchError):
        fetch_feed_items("https://example.com/rss.xml")
