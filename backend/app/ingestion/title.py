import re
from urllib.parse import urlparse

OG_TITLE_PATTERN = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE
)
TITLE_TAG_PATTERN = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)


def extract_title(html: str, url: str) -> str:
    og_match = OG_TITLE_PATTERN.search(html)
    if og_match:
        return og_match.group(1).strip()

    title_match = TITLE_TAG_PATTERN.search(html)
    if title_match:
        return title_match.group(1).strip()

    return urlparse(url).hostname or url
