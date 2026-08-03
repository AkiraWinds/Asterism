import json
from pathlib import Path
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
from app.repositories.config_repository import load_authenticated_hosts  # noqa: F401  (used indirectly via config.json below)

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


# Tests for authenticated host cookie attachment

def _write_authenticated_hosts_config(tmp_path: Path, hosts: dict) -> Path:
    (tmp_path / "config.json").write_text(json.dumps({"authenticated_hosts": hosts}))
    return tmp_path


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_attaches_cookie_for_configured_host(mock_getaddrinfo, tmp_path):
    data_root = _write_authenticated_hosts_config(tmp_path, {"medium.com": "sid=abc; uid=def"})
    response = _response(status_code=200, text="<html>member content</html>", url="https://medium.com/@user/post")
    mock_client = _mock_client([response])
    with patch("app.ingestion.fetcher.httpx.Client", return_value=mock_client):
        result = fetch_url("https://medium.com/@user/post", data_root=data_root)

    assert result == "<html>member content</html>"
    _, kwargs = mock_client.get.call_args
    assert kwargs["headers"]["Cookie"] == "sid=abc; uid=def"


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_omits_cookie_for_unconfigured_host(mock_getaddrinfo, tmp_path):
    data_root = _write_authenticated_hosts_config(tmp_path, {"medium.com": "sid=abc; uid=def"})
    response = _response(status_code=200, text="<html>hi</html>", url="https://example.com/article")
    mock_client = _mock_client([response])
    with patch("app.ingestion.fetcher.httpx.Client", return_value=mock_client):
        fetch_url("https://example.com/article", data_root=data_root)

    _, kwargs = mock_client.get.call_args
    assert "Cookie" not in kwargs["headers"]


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_does_not_carry_cookie_across_redirect_to_different_host(mock_getaddrinfo, tmp_path):
    data_root = _write_authenticated_hosts_config(tmp_path, {"medium.com": "sid=abc; uid=def"})
    redirect_response = _response(
        status_code=302, url="https://medium.com/short", location="https://cdn-other.example.com/article"
    )
    final_response = _response(status_code=200, text="<html>final</html>", url="https://cdn-other.example.com/article")
    mock_client = _mock_client([redirect_response, final_response])
    with patch("app.ingestion.fetcher.httpx.Client", return_value=mock_client):
        fetch_url("https://medium.com/short", data_root=data_root)

    first_call_headers = mock_client.get.call_args_list[0].kwargs["headers"]
    second_call_headers = mock_client.get.call_args_list[1].kwargs["headers"]
    assert first_call_headers["Cookie"] == "sid=abc; uid=def"
    assert "Cookie" not in second_call_headers


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_without_data_root_never_attaches_cookie(mock_getaddrinfo):
    response = _response(status_code=200, text="<html>hi</html>", url="https://medium.com/@user/post")
    mock_client = _mock_client([response])
    with patch("app.ingestion.fetcher.httpx.Client", return_value=mock_client):
        fetch_url("https://medium.com/@user/post")

    _, kwargs = mock_client.get.call_args
    assert "Cookie" not in kwargs["headers"]


def test_fetch_url_raises_login_required_for_x_dot_com_even_with_data_root_when_no_cookie_configured(tmp_path):
    data_root = _write_authenticated_hosts_config(tmp_path, {"medium.com": "sid=abc; uid=def"})
    with patch("app.ingestion.fetcher.httpx.Client") as mock_ctor:
        with pytest.raises(LoginRequiredError):
            fetch_url("https://x.com/someone/status/123", data_root=data_root)
    mock_ctor.assert_not_called()


@patch("app.ingestion.fetcher.socket.getaddrinfo", return_value=PUBLIC_ADDR_INFO)
def test_fetch_url_does_not_raise_login_required_for_x_dot_com_when_cookie_configured(mock_getaddrinfo, tmp_path):
    data_root = _write_authenticated_hosts_config(tmp_path, {"x.com": "auth_token=xyz"})
    response = _response(status_code=200, text="<html>tweet</html>", url="https://x.com/someone/status/123")
    mock_client = _mock_client([response])
    with patch("app.ingestion.fetcher.httpx.Client", return_value=mock_client):
        result = fetch_url("https://x.com/someone/status/123", data_root=data_root)

    assert result == "<html>tweet</html>"
    _, kwargs = mock_client.get.call_args
    assert kwargs["headers"]["Cookie"] == "auth_token=xyz"
