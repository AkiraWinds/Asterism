"""Stable, order-independent hashing of a concept's provenance rows, used to
decide whether an existing wiki page is stale relative to graph.db."""

import hashlib


def provenance_hash(provenance: list[dict]) -> str:
    keys = sorted(f"{row['source_id']}:{row['highlight_id']}" for row in provenance)
    return hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()
