from unittest.mock import MagicMock, patch

import openai
import pytest

from app.providers.base import ProviderConfigError, ProviderError
from app.providers.embeddings import embed_text


def test_embed_text_returns_vector():
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
    )

    with patch("app.providers.embeddings.openai.OpenAI", return_value=mock_client) as mock_ctor:
        result = embed_text("sk-test", "some concept definition")

    assert result == [0.1, 0.2, 0.3]
    mock_ctor.assert_called_once_with(api_key="sk-test")
    _, kwargs = mock_client.embeddings.create.call_args
    assert kwargs["input"] == "some concept definition"
    assert kwargs["model"] == "text-embedding-3-small"


def test_embed_text_raises_config_error_on_authentication_error():
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = openai.AuthenticationError(
        "invalid api key", response=MagicMock(), body=None
    )
    with patch("app.providers.embeddings.openai.OpenAI", return_value=mock_client):
        with pytest.raises(ProviderConfigError):
            embed_text("bad-key", "text")


def test_embed_text_raises_provider_error_on_other_api_error():
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = openai.APIConnectionError(request=MagicMock())
    with patch("app.providers.embeddings.openai.OpenAI", return_value=mock_client):
        with pytest.raises(ProviderError):
            embed_text("sk-test", "text")
