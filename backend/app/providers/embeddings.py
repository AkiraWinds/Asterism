"""OpenAI embeddings, independent of the chat/completion Provider abstraction
(Anthropic has no embeddings endpoint and CLI providers have no embedding
capability, so this always uses OpenAI regardless of the configured chat
provider — see docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md).
"""

import openai

from app.providers.base import ProviderConfigError, ProviderError
from app.repositories.config_repository import DEFAULT_EMBEDDINGS_MODEL

# Re-exported for backward compat with any existing `from .embeddings import
# EMBEDDING_MODEL` import — the actual default now lives in
# config_repository.DEFAULT_EMBEDDINGS_MODEL since that's also where the
# configurable override (config.json's "embeddings_model") is read from.
EMBEDDING_MODEL = DEFAULT_EMBEDDINGS_MODEL


def embed_text(api_key: str, text: str, model: str = DEFAULT_EMBEDDINGS_MODEL) -> list[float]:
    """`model` defaults to DEFAULT_EMBEDDINGS_MODEL for callers (and tests)
    that don't have a data_root handy, but callers with one should load
    config_repository.load_embeddings_model(data_root) and pass it through —
    see that function's docstring for why mixing models mid-graph is unsafe.
    """
    client = openai.OpenAI(api_key=api_key)

    try:
        response = client.embeddings.create(model=model, input=text)
    except openai.AuthenticationError as exc:
        raise ProviderConfigError(str(exc)) from exc
    except openai.APIError as exc:
        raise ProviderError(str(exc)) from exc

    return response.data[0].embedding
