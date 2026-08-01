from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ingestion.fetcher import (
    FetchBlockedError,
    FetchError,
    FetchTimeoutError,
    LoginRequiredError,
    SsrfBlockedError,
    TooManyRedirectsError,
    fetch_url,
)

PUBLIC_ADDR_INFO = [(None, None, None, None, ("93.184.216.34", 0))]


def _addr_info(ip: str):
    return [(None, None, None, None, (ip, 0))]


def _mock_client(get_side_effect):
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.side_effect = get_side_effect
    return mock_client


def _response(status_code=200, text="", url="https://example.com/article", location=None):
    response = MagicMock(status_code=status_code, text=text)
    response.url = httpx.URL(url)
    response.has_redirect_location = location is not None
    response.headers = {"location": location} if location else {}
    return response


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_returns_html_on_success(mock_getaddrinfo):
    response = _response(status_code=200, text="<html>hello</html>")
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client([response])) as mock_ctor:
        result = fetch_url("https://example.com/article")

    assert result == "<html>hello</html>"
    _, kwargs = mock_ctor.call_args
    assert kwargs["timeout"] == 15
    assert kwargs["follow_redirects"] is False


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


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_raises_login_required_when_redirected_to_x_dot_com(mock_getaddrinfo):
    redirect_response = _response(
        status_code=302, url="https://t.co/shortlink", location="https://x.com/someone/status/123"
    )
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client([redirect_response])):
        with pytest.raises(LoginRequiredError):
            fetch_url("https://t.co/shortlink")


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_raises_blocked_on_403(mock_getaddrinfo):
    response = _response(status_code=403, text="", url="https://example.com/blocked")
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client([response])):
        with pytest.raises(FetchBlockedError):
            fetch_url("https://example.com/blocked")


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_raises_fetch_error_on_other_non_2xx(mock_getaddrinfo):
    response = MagicMock(status_code=500, text="")
    response.url = httpx.URL("https://example.com/broken")
    response.has_redirect_location = False
    response.reason_phrase = "Internal Server Error"
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client([response])):
        with pytest.raises(FetchError):
            fetch_url("https://example.com/broken")


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_raises_timeout_error(mock_getaddrinfo):
    with patch(
        "app.ingestion.fetcher.httpx.Client",
        return_value=_mock_client([httpx.TimeoutException("timed out")]),
    ):
        with pytest.raises(FetchTimeoutError):
            fetch_url("https://example.com/slow")


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_raises_fetch_error_on_network_failure(mock_getaddrinfo):
    with patch(
        "app.ingestion.fetcher.httpx.Client",
        return_value=_mock_client([httpx.ConnectError("connection refused")]),
    ):
        with pytest.raises(FetchError):
            fetch_url("https://example.com/unreachable")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "169.254.169.254",  # link-local / cloud metadata
        "10.0.0.5",  # RFC1918 private
        "192.168.1.1",  # RFC1918 private
        "0.0.0.0",  # unspecified
    ],
)
def test_fetch_url_blocks_direct_request_to_non_public_ip(ip):
    with patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=_addr_info(ip)):
        with patch("app.ingestion.fetcher.httpx.Client") as mock_ctor:
            with pytest.raises(SsrfBlockedError):
                fetch_url(f"http://{ip}/")
    mock_ctor.assert_not_called()


def test_fetch_url_blocks_redirect_chain_landing_on_private_ip():
    redirect_response = _response(
        status_code=302, url="https://example.com/redirector", location="http://169.254.169.254/latest/meta-data/"
    )

    def fake_getaddrinfo(hostname, *_args, **_kwargs):
        if hostname == "example.com":
            return PUBLIC_ADDR_INFO
        return _addr_info("169.254.169.254")

    with patch("app.ingestion.fetcher.socket.getaddrinfo", side_effect=fake_getaddrinfo):
        with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client([redirect_response])):
            with pytest.raises(SsrfBlockedError):
                fetch_url("https://example.com/redirector")


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_blocks_non_http_scheme(mock_getaddrinfo):
    with patch("app.ingestion.fetcher.httpx.Client") as mock_ctor:
        with pytest.raises(SsrfBlockedError):
            fetch_url("file:///etc/passwd")
    mock_ctor.assert_not_called()


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_raises_too_many_redirects(mock_getaddrinfo):
    responses = [
        _response(status_code=302, url=f"https://example.com/{i}", location=f"https://example.com/{i + 1}")
        for i in range(7)
    ]
    with patch("app.ingestion.fetcher.httpx.Client", return_value=_mock_client(responses)):
        with pytest.raises(TooManyRedirectsError):
            fetch_url("https://example.com/0")


def test_fetch_url_raises_fetch_error_on_dns_failure():
    import socket

    with patch(
        "app.ingestion.fetcher.socket.getaddrinfo",
        side_effect=socket.gaierror("name resolution failed"),
    ):
        with patch("app.ingestion.fetcher.httpx.Client") as mock_ctor:
            with pytest.raises(FetchError):
                fetch_url("https://does-not-resolve.invalid/")
    mock_ctor.assert_not_called()
