from unittest.mock import MagicMock, patch

import anthropic
import pytest

from app.providers.api_anthropic import AnthropicApiProvider
from app.providers.base import ProviderConfigError, ProviderError


def test_complete_returns_joined_text_blocks():
    provider = AnthropicApiProvider(api_key="sk-test")
    text_block = MagicMock(type="text", text="Hello back")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(content=[text_block])

    with patch("app.providers.api_anthropic.anthropic.Anthropic", return_value=mock_client) as mock_ctor:
        result = provider.complete("Hello")

    assert result == "Hello back"
    mock_ctor.assert_called_once_with(api_key="sk-test")
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]


def test_complete_raises_config_error_on_authentication_error():
    provider = AnthropicApiProvider(api_key="bad-key")
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.AuthenticationError(
        "invalid api key", response=MagicMock(), body=None
    )

    with patch("app.providers.api_anthropic.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(ProviderConfigError):
            provider.complete("Hello")


def test_complete_raises_provider_error_on_other_api_error():
    provider = AnthropicApiProvider(api_key="sk-test")
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())

    with patch("app.providers.api_anthropic.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(ProviderError):
            provider.complete("Hello")
