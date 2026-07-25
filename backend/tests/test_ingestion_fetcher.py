from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ingestion.fetcher import (
    FetchBlockedError,
    FetchError,
    FetchTimeoutError,
    LoginRequiredError,
    fetch_url,
)


def _mock_client(response=None, get_side_effect=None):
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    if get_side_effect is not None:
        mock_client.get.side_effect = get_side_effect
    else:
        mock_client.get.return_value = response
    return mock_client


def test_fetch_url_returns_html_on_success():
    response = MagicMock(status_code=200, text="<html>hello</html>")
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client(response=response)) as mock_ctor:
        result = fetch_url("https://example.com/article")

    assert result == "<html>hello</html>"
    _, kwargs = mock_ctor.call_args
    assert kwargs["timeout"] == 15
    assert kwargs["follow_redirects"] is True


def test_fetch_url_raises_login_required_for_x_dot_com_without_any_http_call():
    with patch("app.ingestion.fetcher.httpx.Client") as mock_ctor:
        with pytest.raises(LoginRequiredError):
            fetch_url("https://x.com/someone/status/123")
    mock_ctor.assert_not_called()


def test_fetch_url_raises_login_required_for_twitter_dot_com():
    with patch("app.ingestion.fetcher.httpx.Client") as mock_ctor:
        with pytest.raises(LoginRequiredError):
            fetch_url("https://twitter.com/someone")
    mock_ctor.assert_not_called()


def test_fetch_url_raises_blocked_on_403():
    response = MagicMock(status_code=403, text="")
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client(response=response)):
        with pytest.raises(FetchBlockedError):
            fetch_url("https://example.com/blocked")


def test_fetch_url_raises_fetch_error_on_other_non_2xx():
    response = MagicMock(status_code=500, reason_phrase="Internal Server Error", text="")
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client(response=response)):
        with pytest.raises(FetchError):
            fetch_url("https://example.com/broken")


def test_fetch_url_raises_timeout_error():
    with patch(
        "app.ingestion.fetcher.httpx.Client",
        return_value=_mock_client(get_side_effect=httpx.TimeoutException("timed out")),
    ):
        with pytest.raises(FetchTimeoutError):
            fetch_url("https://example.com/slow")


def test_fetch_url_raises_fetch_error_on_network_failure():
    with patch(
        "app.ingestion.fetcher.httpx.Client",
        return_value=_mock_client(get_side_effect=httpx.ConnectError("connection refused")),
    ):
        with pytest.raises(FetchError):
            fetch_url("https://example.com/unreachable")
