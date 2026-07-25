import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 15
LOGIN_REQUIRED_HOSTS = {"x.com", "twitter.com"}


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


def fetch_url(url: str) -> str:
    hostname = (httpx.URL(url).host or "").lower()
    if hostname in LOGIN_REQUIRED_HOSTS:
        raise LoginRequiredError(
            f"{hostname} requires login to view content. Please capture it with the "
            "Chrome Extension while logged in."
        )

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            response = client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,image/apng,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
    except httpx.TimeoutException as exc:
        raise FetchTimeoutError(f"Request to {url} timed out after {TIMEOUT_SECONDS}s") from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc

    if response.status_code == 403:
        raise FetchBlockedError("This site blocks automated requests.")
    if response.status_code >= 400:
        raise FetchError(f"Failed to fetch URL: {response.status_code} {response.reason_phrase}")

    return response.text
