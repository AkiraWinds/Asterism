import re
from pathlib import Path

import trafilatura

from app.providers.factory import build_provider
from app.repositories.config_repository import load_config

MIN_LENGTH = 500
MAX_HTML_CHARS = 120_000

EXTRACTION_PROMPT_TEMPLATE = (
    "Extract the main readable article content from the following HTML and return "
    "it as clean Markdown. Preserve headings, paragraphs, images, and tables where "
    "present. Preserve every inline hyperlink as Markdown link syntax "
    "[text](url) using each anchor's href — do not drop links or flatten them to "
    "plain text. Preserve every content <img> as Markdown image syntax ![alt](url) "
    "using that img's actual src — never replace an image with a text description or "
    "placeholder caption. Preserve every <table> as a Markdown pipe table with the "
    "same rows/columns — never drop a table or summarize it as prose. Return only the "
    "Markdown, no commentary.\n\nHTML:\n{html}"
)

# trafilatura has two verified blind spots that silently drop real content while
# still returning a "long enough" result, so the length check below can't catch them:
#   1. It discards any element whose class matches its generic embed/boilerplate
#      regex (trafilatura/xpaths.py DISCARD list, which includes "embed"). Several
#      CMSes — e.g. Webflow's `w-embed` wrapper class — use that name for ordinary
#      content containers (tables, code blocks), not ads/social embeds, so real
#      tables get stripped along with the junk.
#   2. Its image allowlist (trafilatura/utils.py IMAGE_EXTENSION) only matches
#      raster formats (png/jpg/webp/...) — an <img src="*.svg"> is never extracted,
#      so SVG diagrams vanish even though the article's prose survives intact.
# Both are upstream trafilatura behaviors we can't fix by tweaking its call
# arguments, so instead of writing brittle HTML-repair code we just detect that
# a table or SVG image present in the raw HTML didn't make it into the output,
# and hand the raw HTML to the AI extractor (whose prompt already asks for tables
# and images) to interpret instead.
_TABLE_TAG_RE = re.compile(r"<table\b", re.IGNORECASE)
_MARKDOWN_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
_SVG_IMAGE_SRC_RE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+\.svg\b[^"\']*)["\']', re.IGNORECASE)


def _dropped_structural_content(html: str, extracted: str) -> bool:
    if _TABLE_TAG_RE.search(html) and not _MARKDOWN_TABLE_ROW_RE.search(extracted):
        return True
    return any(src not in extracted for src in _SVG_IMAGE_SRC_RE.findall(html))


def extract_content(html: str, url: str, data_root: Path) -> str:
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_images=True,
        include_links=True,
    )

    if extracted and len(extracted) > MIN_LENGTH and not _dropped_structural_content(html, extracted):
        return extracted

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(html=html[:MAX_HTML_CHARS])
    config = load_config(data_root)
    provider = build_provider(config, data_root)
    return provider.complete(prompt)
