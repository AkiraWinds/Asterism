from pathlib import Path

import trafilatura

from app.providers.factory import build_provider
from app.repositories.config_repository import load_config

MIN_LENGTH = 500
MAX_HTML_CHARS = 120_000

EXTRACTION_PROMPT_TEMPLATE = (
    "Extract the main readable article content from the following HTML and return "
    "it as clean Markdown. Preserve headings, paragraphs, links, images, and tables "
    "where present. Return only the Markdown, no commentary.\n\nHTML:\n{html}"
)


def extract_content(html: str, url: str, data_root: Path) -> str:
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_images=True,
    )

    if extracted and len(extracted) > MIN_LENGTH:
        return extracted

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(html=html[:MAX_HTML_CHARS])
    config = load_config(data_root)
    provider = build_provider(config, data_root)
    return provider.complete(prompt)
