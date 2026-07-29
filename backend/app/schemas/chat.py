"""Pydantic models for Phase 5 chat: the shape of chat.json (ChatTurn, ChatHistory)
and the chat request body (ChatRequest). See
docs/superpowers/specs/2026-07-29-chat-copilot-design.md for the full design.
"""

from typing import Literal

from pydantic import BaseModel


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    attached_highlight: str | None = None
    # Set on an assistant turn that was cut short by a mid-stream provider
    # error, so the frontend can render it distinctly on reload instead of
    # looking like a normal completed reply.
    truncated: bool = False
    created_at: str


class ChatHistory(BaseModel):
    turns: list[ChatTurn] = []


class ChatRequest(BaseModel):
    message: str
    attached_highlight: str | None = None
