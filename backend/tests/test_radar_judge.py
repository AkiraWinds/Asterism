import pytest

from app.providers.base import Provider
from app.radar.judge import JudgeError, build_judge_prompt, judge_item, parse_judge_response


class _StubProvider(Provider):
    def __init__(self, responses: list[str]):
        self._responses = responses
        self.calls = 0

    def complete(self, prompt: str) -> str:
        response = self._responses[self.calls]
        self.calls += 1
        return response


def test_build_judge_prompt_includes_rubric_dimensions_and_context():
    prompt = build_judge_prompt("Article text here.", "OpenAI Blog", ["AI agents", "loop engineering"])
    assert "OpenAI Blog" in prompt
    assert "AI agents" in prompt
    assert "originality" in prompt.lower()
    assert "depth" in prompt.lower() or "comprehensive" in prompt.lower()


def test_parse_judge_response_strips_markdown_fence():
    raw = '```json\n{"relevance_score": 0.8, "quality_score": 0.6, "reasoning": "Matches your interests."}\n```'
    result = parse_judge_response(raw)
    assert result == {"relevance_score": 0.8, "quality_score": 0.6, "reasoning": "Matches your interests."}


def test_parse_judge_response_rejects_out_of_range_scores():
    raw = '{"relevance_score": 1.5, "quality_score": 0.6, "reasoning": "x"}'
    with pytest.raises(ValueError):
        parse_judge_response(raw)


def test_judge_item_retries_once_on_malformed_response_then_succeeds():
    provider = _StubProvider([
        "not json at all",
        '{"relevance_score": 0.7, "quality_score": 0.5, "reasoning": "Solid technical depth."}',
    ])

    result = judge_item(provider, "Article text.", "LangChain Blog", ["agents"])

    assert result["relevance_score"] == 0.7
    assert provider.calls == 2


def test_judge_item_raises_after_exhausting_retries():
    provider = _StubProvider(["not json", "still not json"])

    with pytest.raises(JudgeError):
        judge_item(provider, "Article text.", "LangChain Blog", ["agents"])
