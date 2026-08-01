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


class Conversation(BaseModel):
    """A single chat thread for a source. Multiple conversations live side by
    side under library/{id}/chat/{conversation_id}.json, replacing the old
    single library/{id}/chat.json (auto-migrated on first read, see
    source_repository.list_conversations)."""

    id: str
    title: str
    created_at: str
    updated_at: str
    turns: list[ChatTurn] = []


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turn_count: int


class DeleteConversationResponse(BaseModel):
    # Non-null only when deleting the last remaining conversation: a source
    # must always have at least one chat thread, so the delete endpoint
    # creates and returns a fresh replacement rather than leaving zero.
    replacement: ConversationSummary | None = None
