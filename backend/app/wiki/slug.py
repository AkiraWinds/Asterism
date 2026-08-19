"""Filename slug generation for wiki pages."""

import re


def slugify(term: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    return slug or "concept"


def unique_slug(term: str, concept_id: str, taken_slugs: set[str]) -> str:
    base = slugify(term)
    if base not in taken_slugs:
        return base
    return f"{base}-{concept_id[-6:]}"


def aspect_slug(concept_slug: str, aspect_title: str, taken_slugs: set[str]) -> str:
    """Aspect titles are invented fresh by the LLM on every compile run (no
    stable id like a concept has), so collisions are resolved with a plain
    numeric suffix rather than unique_slug()'s concept-id suffix."""
    base = f"{concept_slug}-{slugify(aspect_title)}"
    if base not in taken_slugs:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken_slugs:
        suffix += 1
    return f"{base}-{suffix}"
