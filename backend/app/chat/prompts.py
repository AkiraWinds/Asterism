"""Prompt assembly for Phase 5 chat: flattens source content, optional analysis,
conversation history, and an optional attached highlight into the single prompt
string Provider.complete/stream_complete expect (providers are flat
prompt-in/text-out, not message-array based — see
docs/superpowers/specs/2026-07-29-chat-copilot-design.md).
"""

from app.schemas.analysis import AnalysisResult
from app.schemas.chat import ChatTurn


def build_chat_prompt(
    content: str,
    analysis: AnalysisResult | None,
    history: list[ChatTurn],
    attached_highlight: str | None,
    message: str,
) -> str:
    parts = [
        "You are a helpful assistant discussing a single saved article with the user. "
        "Answer using the article content and analysis below as your primary context.",
        f"## Article content\n\n{content}",
    ]

    if analysis is not None and analysis.digest is not None:
        parts.append(f"## Existing summary\n\n{analysis.digest.summary}")

    if history:
        turns_text = "\n".join(f"{turn.role}: {turn.content}" for turn in history)
        parts.append(f"## Conversation so far\n\n{turns_text}")

    if attached_highlight:
        parts.append(f"## User highlighted this passage\n\n{attached_highlight}")

    parts.append(f"## New message\n\nuser: {message}")

    return "\n\n".join(parts)
