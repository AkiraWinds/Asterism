import pytest

from app.analysis.parsing import NodeOutputError, extract_json


def test_extract_json_plain_object():
    assert extract_json('{"score": 78}') == {"score": 78}


def test_extract_json_with_code_fence():
    text = '```json\n{"score": 78}\n```'
    assert extract_json(text) == {"score": 78}


def test_extract_json_with_leading_and_trailing_prose():
    text = 'Sure, here is the analysis:\n{"score": 78}\nLet me know if you need anything else.'
    assert extract_json(text) == {"score": 78}


def test_extract_json_with_nested_braces():
    text = '{"digest": {"summary": "A summary with {braces} inside a string."}}'
    result = extract_json(text)
    assert result["digest"]["summary"] == "A summary with {braces} inside a string."


def test_extract_json_raises_when_no_object_present():
    with pytest.raises(NodeOutputError):
        extract_json("I could not analyze this content.")


def test_extract_json_raises_on_malformed_json():
    with pytest.raises(NodeOutputError):
        extract_json('{"score": 78,}')


def test_extract_json_raises_on_unbalanced_braces():
    with pytest.raises(NodeOutputError):
        extract_json('{"score": 78')
