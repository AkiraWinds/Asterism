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
