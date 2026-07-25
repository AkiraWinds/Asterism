from unittest.mock import MagicMock, patch

import openai
import pytest

from app.providers.api_openai import OpenAiApiProvider
from app.providers.base import ProviderConfigError, ProviderError


def test_complete_returns_message_content():
    provider = OpenAiApiProvider(api_key="sk-test")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Hello back"))]
    )

    with patch("app.providers.api_openai.openai.OpenAI", return_value=mock_client) as mock_ctor:
        result = provider.complete("Hello")

    assert result == "Hello back"
    mock_ctor.assert_called_once_with(api_key="sk-test")
    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]


def test_complete_raises_config_error_on_authentication_error():
    provider = OpenAiApiProvider(api_key="bad-key")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
        "invalid api key", response=MagicMock(), body=None
    )

    with patch("app.providers.api_openai.openai.OpenAI", return_value=mock_client):
        with pytest.raises(ProviderConfigError):
            provider.complete("Hello")


def test_complete_raises_provider_error_on_other_api_error():
    provider = OpenAiApiProvider(api_key="sk-test")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = openai.APIConnectionError(request=MagicMock())

    with patch("app.providers.api_openai.openai.OpenAI", return_value=mock_client):
        with pytest.raises(ProviderError):
            provider.complete("Hello")
