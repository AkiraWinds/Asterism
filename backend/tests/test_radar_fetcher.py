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
    monkeypatch.setattr("app.radar.fetcher.fetch_url", lambda url, **kwargs: _SAMPLE_RSS)

    items = fetch_feed_items("https://example.com/rss.xml")

    assert len(items) == 2
    assert items[0]["url"] == "https://example.com/post-one"
    assert items[0]["title"] == "Post One"
    assert items[0]["summary"] == "A summary of post one."
    assert items[0]["published_at"] is not None
    assert items[1]["published_at"] is None  # no pubDate on the second item


def test_fetch_feed_items_raises_on_fetch_error(monkeypatch):
    from app.ingestion.fetcher import FetchError

    def _raise(url, **kwargs):
        raise FetchError("connection refused")

    monkeypatch.setattr("app.radar.fetcher.fetch_url", _raise)

    with pytest.raises(FeedFetchError):
        fetch_feed_items("https://example.com/rss.xml")


def test_fetch_feed_items_raises_on_unparseable_content(monkeypatch):
    monkeypatch.setattr("app.radar.fetcher.fetch_url", lambda url, **kwargs: "not xml at all, just plain text")

    with pytest.raises(FeedFetchError):
        fetch_feed_items("https://example.com/rss.xml")


def test_fetch_feed_items_wraps_body_in_bytesio_before_parsing(monkeypatch):
    # feedparser.parse() treats a raw str argument as a URL-or-filename BEFORE
    # treating it as feed data — if fetch_url's body happened to look like a
    # URL (e.g. an SSRF-targeting cloud metadata address), passing it straight
    # through would let feedparser fetch THAT itself with zero SSRF
    # protection. The fix wraps the body in io.BytesIO so feedparser takes its
    # "already have data" path instead. Assert directly on what feedparser.parse
    # is called with, rather than on end-to-end behavior — a prior version of
    # this test asserted only that FeedFetchError was raised, which happens to
    # be true whether or not the BytesIO wrap is present (in a network-sandboxed
    # test run, feedparser trying to fetch the URL itself also fails and also
    # produces a bozo/no-entries result), so it never actually caught a
    # regression.
    monkeypatch.setattr(
        "app.radar.fetcher.fetch_url", lambda url, **kwargs: "http://169.254.169.254/latest/meta-data/"
    )

    captured = {}

    def _fake_parse(data):
        captured["data"] = data
        captured["is_str"] = isinstance(data, str)
        # Return something with no usable entries, same as the real parse
        # result for this non-XML input, so fetch_feed_items still raises.
        class _Result:
            bozo = True
            bozo_exception = Exception("not valid feed XML")
            entries = []

        return _Result()

    monkeypatch.setattr("app.radar.fetcher.feedparser.parse", _fake_parse)

    with pytest.raises(FeedFetchError):
        fetch_feed_items("https://example.com/rss.xml")

    # The actual assertion that discriminates the fix: feedparser.parse must
    # never be called with a raw str (which it would treat as a URL/filename
    # to fetch itself) — it must be called with a file-like object instead.
    assert captured["is_str"] is False
    assert hasattr(captured["data"], "read")
