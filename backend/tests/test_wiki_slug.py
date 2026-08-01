from app.wiki.slug import aspect_slug, slugify, unique_slug


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


def test_aspect_slug_combines_concept_slug_and_title():
    assert aspect_slug("retrieval-augmented-generation", "Evaluation", set()) == (
        "retrieval-augmented-generation-evaluation"
    )


def test_aspect_slug_suffixes_numerically_on_collision():
    taken = {"rag-evaluation"}
    assert aspect_slug("rag", "Evaluation", taken) == "rag-evaluation-2"


def test_aspect_slug_keeps_incrementing_past_first_collision():
    taken = {"rag-evaluation", "rag-evaluation-2"}
    assert aspect_slug("rag", "Evaluation", taken) == "rag-evaluation-3"
