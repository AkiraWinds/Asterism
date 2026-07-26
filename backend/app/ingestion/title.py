import re
from urllib.parse import urlparse

# Match any meta tag with arbitrary attributes
META_TAG_PATTERN = re.compile(r"<meta[^>]*>", re.IGNORECASE)
# Extract content attribute value with matching quotes
CONTENT_ATTR_PATTERN = re.compile(r'content\s*=\s*(["\'])(.*?)\1', re.IGNORECASE)
TITLE_TAG_PATTERN = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)


def _extract_og_title(html: str) -> str | None:
    """Extract og:title from meta tags, handling arbitrary attribute order and quote matching."""
    for meta_match in META_TAG_PATTERN.finditer(html):
        meta_tag = meta_match.group(0)
        # Check if this meta tag contains property="og:title" (order-independent, case-insensitive)
        # Use case-insensitive search to find property attribute with og:title value
        if re.search(r'property\s*=\s*["\']og:title["\']', meta_tag, re.IGNORECASE):
            # Extract content attribute with matching quote characters
            content_match = CONTENT_ATTR_PATTERN.search(meta_tag)
            if content_match:
                return content_match.group(2).strip()
    return None


def extract_title(html: str, url: str) -> str:
    og_title = _extract_og_title(html)
    if og_title:
        return og_title

    title_match = TITLE_TAG_PATTERN.search(html)
    if title_match:
        title_text = title_match.group(1).strip()
        if title_text:
            return title_text

    return urlparse(url).hostname or url
