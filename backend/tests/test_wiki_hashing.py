from app.wiki.hashing import provenance_hash


def test_same_rows_different_order_produce_same_hash():
    a = [{"source_id": "s_1", "highlight_id": "h_1"}, {"source_id": "s_2", "highlight_id": "h_2"}]
    b = [{"source_id": "s_2", "highlight_id": "h_2"}, {"source_id": "s_1", "highlight_id": "h_1"}]
    assert provenance_hash(a) == provenance_hash(b)


def test_different_rows_produce_different_hash():
    a = [{"source_id": "s_1", "highlight_id": "h_1"}]
    b = [{"source_id": "s_1", "highlight_id": "h_2"}]
    assert provenance_hash(a) != provenance_hash(b)


def test_empty_provenance_is_stable():
    assert provenance_hash([]) == provenance_hash([])
