from app.wiki.selection import MIN_PROVENANCE_COUNT, select_qualifying_concepts


def test_min_provenance_count_is_three():
    assert MIN_PROVENANCE_COUNT == 3


def test_select_qualifying_concepts_filters_by_threshold():
    concepts = [{"id": "c_1"}, {"id": "c_2"}]
    provenance_by_concept = {
        "c_1": [{"source_id": "s_1", "highlight_id": "h_1"}] * 3,
        "c_2": [{"source_id": "s_1", "highlight_id": "h_1"}],
    }
    result = select_qualifying_concepts(concepts, provenance_by_concept)
    assert [c["id"] for c in result] == ["c_1"]


def test_select_qualifying_concepts_treats_missing_entry_as_zero():
    concepts = [{"id": "c_1"}]
    result = select_qualifying_concepts(concepts, {})
    assert result == []
