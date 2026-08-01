import httpx
import pytest

from app.providers.base import ProviderError
from app.search.brave import search_web


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json_body = json_body
        self.text = str(json_body)

    def json(self):
        return self._json_body


def test_search_web_returns_parsed_results(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, {
            "web": {"results": [
                {"title": "Agentic AI", "url": "https://example.com/a", "description": "An overview."},
            ]}
        })
    monkeypatch.setattr(httpx, "get", fake_get)

    results = search_web("fake-key", "Agentic AI")

    assert results == [{"title": "Agentic AI", "url": "https://example.com/a", "description": "An overview."}]


def test_search_web_returns_empty_list_when_no_results(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, {"web": {"results": []}})
    monkeypatch.setattr(httpx, "get", fake_get)

    assert search_web("fake-key", "a very obscure query") == []


def test_search_web_raises_provider_error_on_non_2xx(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(401, {"error": "bad key"})
    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(ProviderError):
        search_web("bad-key", "Agentic AI")
