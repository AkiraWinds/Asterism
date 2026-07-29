import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatHistory, ChatRequest, ChatTurn


def test_chat_turn_defaults():
    turn = ChatTurn(role="user", content="hello", created_at="2026-07-29T12:00:00Z")

    assert turn.attached_highlight is None
    assert turn.truncated is False


def test_chat_turn_rejects_invalid_role():
    with pytest.raises(ValidationError):
        ChatTurn(role="system", content="hello", created_at="2026-07-29T12:00:00Z")


def test_chat_history_defaults_to_empty_list():
    history = ChatHistory()

    assert history.turns == []


def test_chat_request_requires_message():
    with pytest.raises(ValidationError):
        ChatRequest()

    request = ChatRequest(message="hi")
    assert request.attached_highlight is None
