import re
from pathlib import Path

import trafilatura

from app.providers.factory import build_provider
from app.repositories.config_repository import load_config

MIN_LENGTH = 500
MAX_HTML_CHARS = 120_000

# A literal sentinel the AI extractor is instructed to return verbatim when the HTML it was
# given has no article to extract, instead of prose explaining why. Without this, a model's
# refusal text ("I don't see an article body here...") reads exactly like any other successful
# extraction — MIN_LENGTH-worthy prose — and gets silently persisted as the source's content
# (see AGENTS.md: caught live when _main_content_region's fix above still left an AI-fallback
# path that could see a genuinely content-free page). Checking for a fixed token the model
# emits on purpose is a real signal; grepping its prose for refusal-sounding phrases across
# providers/models would not be.
NO_CONTENT_SENTINEL = "NO_CONTENT_FOUND"

EXTRACTION_PROMPT_TEMPLATE = (
    "Extract the main readable article content from the following HTML and return "
    "it as clean Markdown. Preserve headings, paragraphs, images, and tables where "
    "present. Preserve every inline hyperlink as Markdown link syntax "
    "[text](url) using each anchor's href — do not drop links or flatten them to "
    "plain text. Preserve every content <img> as Markdown image syntax ![alt](url) "
    "using that img's actual src — never replace an image with a text description or "
    "placeholder caption. Preserve every <table> as a Markdown pipe table with the "
    "same rows/columns — never drop a table or summarize it as prose. Return only the "
    f"Markdown, no commentary. If (and only if) this HTML has no article/content body to "
    f"extract — e.g. it's only a header, navigation, or search UI — respond with exactly "
    f"{NO_CONTENT_SENTINEL} and nothing else, rather than explaining why.\n\nHTML:\n{{html}}"
)


class ExtractionFailedError(Exception):
    """Raised when the AI extractor reports (via NO_CONTENT_SENTINEL) that the given HTML has
    no article content — e.g. a capture taken before an SPA finished rendering. Callers should
    surface this as a real ingestion failure rather than persisting the sentinel/prose as
    content, which would otherwise dedupe every future re-capture attempt against garbage."""

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
# 3. A third blind spot, found live on a docs site using Shiki/Prism-style syntax
#    highlighting: each line of a code sample is wrapped in its own <span class="line">,
#    with per-token <span style="color:..."> nested inside that. On a large enough page (a
#    code-heavy tutorial with several such blocks — reproduced on the real page, not on a
#    small isolated fixture, so this is a whole-document effect rather than a per-block one)
#    trafilatura's markdown writer stops recognizing these as <pre> content at all and joins
#    every line span with a space like ordinary inline text, so a whole multi-line function
#    round-trips as one giant line wrapped in a single inline `code` span — real content,
#    genuinely present in the output, just missing every line break.
_TABLE_TAG_RE = re.compile(r"<table\b", re.IGNORECASE)
_MARKDOWN_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
_SVG_IMAGE_SRC_RE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+\.svg\b[^"\']*)["\']', re.IGNORECASE)
_PRE_TAG_RE = re.compile(r"<pre\b.*?</pre>", re.IGNORECASE | re.DOTALL)
_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_MAIN_CONTENT_RE = re.compile(r"<main\b.*?</main>|<article\b.*?</article>", re.IGNORECASE | re.DOTALL)

# A <pre> with fewer lines than this isn't worth escalating to the AI extractor over even if
# it does get flattened — the content loss is trivial and the AI-fallback's own cost (a full
# provider call) isn't worth paying for it.
MIN_MULTILINE_CODE_LINES = 3


def _main_content_region(html: str) -> str:
    """Return the page's <main>/<article> region(s), or the whole document if it has neither.

    Docs/blog sites routinely put a full site-nav tree, a header logo, and search UI ahead of
    the actual article in DOM order — often tens or hundreds of KB of markup. Two things need
    to look only at the article itself rather than the whole page:
      1. `_dropped_structural_content`'s table/SVG check — otherwise a decorative image in the
         header (e.g. a site logo <img src="logo.svg">, which trafilatura correctly never
         includes in article output) reads as "trafilatura dropped real content" and forces
         every page using that logo through the AI-extraction fallback for no reason.
      2. The AI-extraction fallback's own input — `html[:MAX_HTML_CHARS]` from the start of a
         page whose nav tree alone exceeds MAX_HTML_CHARS truncates before the article even
         begins, so the model is only ever shown chrome and (correctly) refuses to fabricate
         a body it was never given.
    <main>/<article> are the standard HTML5 landmarks for "this is the content", so scoping to
    them (falling back to the full page when neither is present) generalizes across sites
    without hardcoding any site-specific selector.
    """
    matches = _MAIN_CONTENT_RE.findall(html)
    return "".join(matches) if matches else html


def _dropped_structural_content(html: str, extracted: str) -> bool:
    content_html = _main_content_region(html)
    if _TABLE_TAG_RE.search(content_html) and not _MARKDOWN_TABLE_ROW_RE.search(extracted):
        return True
    return any(src not in extracted for src in _SVG_IMAGE_SRC_RE.findall(content_html))


def _dropped_multiline_code(html: str, extracted: str) -> bool:
    content_html = _main_content_region(html)
    has_multiline_pre = any(
        pre.count("\n") >= MIN_MULTILINE_CODE_LINES for pre in _PRE_TAG_RE.findall(content_html)
    )
    if not has_multiline_pre:
        return False
    return not any(block.count("\n") >= 2 for block in _FENCED_CODE_BLOCK_RE.findall(extracted))


def extract_content(html: str, url: str, data_root: Path) -> str:
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_images=True,
        include_links=True,
    )

    if (
        extracted
        and len(extracted) > MIN_LENGTH
        and not _dropped_structural_content(html, extracted)
        and not _dropped_multiline_code(html, extracted)
    ):
        return extracted

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(html=_main_content_region(html)[:MAX_HTML_CHARS])
    config = load_config(data_root)
    provider = build_provider(config, data_root)
    result = provider.complete(prompt)
    if result.strip() == NO_CONTENT_SENTINEL:
        raise ExtractionFailedError(
            "The AI extractor found no article content in the captured HTML — the page may "
            "not have finished loading before it was captured. Try reloading the page and "
            "capturing again."
        )
    return result
