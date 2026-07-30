"""OpenAI embeddings, independent of the chat/completion Provider abstraction
(Anthropic has no embeddings endpoint and CLI providers have no embedding
capability, so this always uses OpenAI regardless of the configured chat
provider — see docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md).
"""

import openai

from app.providers.base import ProviderConfigError, ProviderError

EMBEDDING_MODEL = "text-embedding-3-small"


def embed_text(api_key: str, text: str) -> list[float]:
    client = openai.OpenAI(api_key=api_key)

    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    except openai.AuthenticationError as exc:
        raise ProviderConfigError(str(exc)) from exc
    except openai.APIError as exc:
        raise ProviderError(str(exc)) from exc

    return response.data[0].embedding
