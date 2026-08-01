import ipaddress
import socket

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 15
LOGIN_REQUIRED_HOSTS = {"x.com", "twitter.com"}
MAX_REDIRECTS = 5
ALLOWED_SCHEMES = {"http", "https"}


class FetchError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LoginRequiredError(FetchError):
    pass


class FetchBlockedError(FetchError):
    pass


class FetchTimeoutError(FetchError):
    pass


class SsrfBlockedError(FetchError):
    pass


class TooManyRedirectsError(FetchError):
    pass


def _check_login_required(hostname: str) -> None:
    if hostname in LOGIN_REQUIRED_HOSTS:
        raise LoginRequiredError(
            f"{hostname} requires login to view content. Please capture it with the "
            "Chrome Extension while logged in."
        )


def _check_ip_safe(hostname: str) -> None:
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve host: {hostname}") from exc

    for *_rest, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise SsrfBlockedError(
                f"{hostname} resolves to a non-public address ({ip}) and cannot be fetched."
            )


def _check_url_safe(url: httpx.URL) -> None:
    if url.scheme not in ALLOWED_SCHEMES:
        raise SsrfBlockedError(f"URL scheme '{url.scheme}' is not allowed.")
    hostname = (url.host or "").lower()
    _check_login_required(hostname)
    _check_ip_safe(hostname)


def fetch_url(url: str) -> str:
    next_url = httpx.URL(url)
    _check_url_safe(next_url)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                response = client.get(next_url, headers=headers)

                if not response.has_redirect_location:
                    break

                next_url = response.url.join(response.headers["location"])
                _check_url_safe(next_url)
            else:
                raise TooManyRedirectsError(f"Exceeded {MAX_REDIRECTS} redirects fetching {url}")
    except httpx.TimeoutException as exc:
        raise FetchTimeoutError(f"Request to {url} timed out after {TIMEOUT_SECONDS}s") from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc

    if response.status_code == 403:
        raise FetchBlockedError("This site blocks automated requests.")
    if response.status_code >= 400:
        raise FetchError(f"Failed to fetch URL: {response.status_code} {response.reason_phrase}")

    return response.text
