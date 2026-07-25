from pathlib import Path

from app.providers.api_anthropic import AnthropicApiProvider
from app.providers.api_openai import OpenAiApiProvider
from app.providers.base import Provider
from app.providers.cli_claude import ClaudeCliProvider
from app.providers.cli_codex import CodexCliProvider
from app.repositories.config_repository import AgentConfig


def build_provider(config: AgentConfig, data_root: Path) -> Provider:
    if config.strategy == "cli":
        if config.provider == "claude":
            return ClaudeCliProvider()
        return CodexCliProvider(data_root=data_root)

    if config.provider == "anthropic":
        return AnthropicApiProvider(api_key=config.api_key)
    return OpenAiApiProvider(api_key=config.api_key)
