from app.wiki.lint import find_orphan_concepts, find_unexplained_contradictions


def test_find_orphan_concepts_returns_untouched_concepts():
    concepts = [{"id": "c_1"}, {"id": "c_2"}]
    edges = [{"from_id": "c_1", "to_id": "c_3", "type": "related", "summary": ""}]
    orphans = find_orphan_concepts(concepts, edges)
    assert [c["id"] for c in orphans] == ["c_2"]


def test_find_orphan_concepts_empty_when_all_touched():
    concepts = [{"id": "c_1"}, {"id": "c_2"}]
    edges = [{"from_id": "c_1", "to_id": "c_2", "type": "related", "summary": ""}]
    assert find_orphan_concepts(concepts, edges) == []


def test_find_unexplained_contradictions_flags_when_neither_page_mentions_other():
    edges = [{"from_id": "c_1", "to_id": "c_2", "type": "contradicts", "summary": "disputes it"}]
    page_bodies = {"c_1": "RAG improves grounding.", "c_2": "Fine-tuning bakes knowledge in."}
    concept_terms = {"c_1": "RAG", "c_2": "Fine-tuning"}

    flagged = find_unexplained_contradictions(edges, page_bodies, concept_terms)

    assert len(flagged) == 1


def test_find_unexplained_contradictions_skips_when_one_page_mentions_other():
    edges = [{"from_id": "c_1", "to_id": "c_2", "type": "contradicts", "summary": "disputes it"}]
    page_bodies = {"c_1": "RAG contradicts Fine-tuning's static-knowledge assumption.", "c_2": "Fine-tuning bakes knowledge in."}
    concept_terms = {"c_1": "RAG", "c_2": "Fine-tuning"}

    flagged = find_unexplained_contradictions(edges, page_bodies, concept_terms)

    assert flagged == []


def test_find_unexplained_contradictions_skips_when_endpoint_has_no_page():
    edges = [{"from_id": "c_1", "to_id": "c_2", "type": "contradicts", "summary": ""}]
    page_bodies = {"c_1": "RAG improves grounding."}
    concept_terms = {"c_1": "RAG", "c_2": "Fine-tuning"}

    assert find_unexplained_contradictions(edges, page_bodies, concept_terms) == []


def test_find_unexplained_contradictions_ignores_non_contradicts_edges():
    edges = [{"from_id": "c_1", "to_id": "c_2", "type": "related", "summary": ""}]
    page_bodies = {"c_1": "a", "c_2": "b"}
    concept_terms = {"c_1": "A", "c_2": "B"}
    assert find_unexplained_contradictions(edges, page_bodies, concept_terms) == []
