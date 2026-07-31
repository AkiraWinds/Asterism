from app.wiki.slug import slugify, unique_slug


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Retrieval-Augmented Generation") == "retrieval-augmented-generation"


def test_slugify_strips_non_alnum():
    assert slugify("GraphRAG (v2)!") == "graphrag-v2"


def test_slugify_falls_back_when_empty():
    assert slugify("!!!") == "concept"


def test_unique_slug_returns_base_when_free():
    assert unique_slug("RAG", "c_abc123", set()) == "rag"


def test_unique_slug_suffixes_on_collision():
    taken = {"rag"}
    assert unique_slug("RAG", "c_abc123456", taken) == "rag-123456"
