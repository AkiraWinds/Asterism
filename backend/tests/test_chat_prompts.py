from app.chat.prompts import build_chat_prompt
from app.schemas.analysis import AnalysisResult, Digest, Triage
from app.schemas.chat import ChatTurn


def _triage():
    return Triage(score=70, action="worth_reading", reason="x", read_time_minutes=5, density=60, originality=50)


def test_prompt_includes_source_content_and_new_message():
    prompt = build_chat_prompt(content="The article body.", analysis=None, history=[], attached_highlight=None, message="What is this about?")

    assert "The article body." in prompt
    assert "What is this about?" in prompt


def test_prompt_includes_analysis_when_present():
    analysis = AnalysisResult(triage=_triage(), digest=Digest(summary="A summary of the piece."), analyzed_at="2026-07-29T00:00:00Z")

    prompt = build_chat_prompt(content="Body.", analysis=analysis, history=[], attached_highlight=None, message="Q")

    assert "A summary of the piece." in prompt


def test_prompt_omits_analysis_section_when_none():
    prompt = build_chat_prompt(content="Body.", analysis=None, history=[], attached_highlight=None, message="Q")

    assert "summary" not in prompt.lower()


def test_prompt_includes_prior_turns_in_order():
    history = [
        ChatTurn(role="user", content="First question", created_at="2026-07-29T12:00:00Z"),
        ChatTurn(role="assistant", content="First answer", created_at="2026-07-29T12:00:01Z"),
    ]

    prompt = build_chat_prompt(content="Body.", analysis=None, history=history, attached_highlight=None, message="Second question")

    assert prompt.index("First question") < prompt.index("First answer") < prompt.index("Second question")


def test_prompt_includes_attached_highlight():
    prompt = build_chat_prompt(content="Body.", analysis=None, history=[], attached_highlight="a quoted passage", message="Q")

    assert "a quoted passage" in prompt
