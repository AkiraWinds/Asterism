from pathlib import Path

from app.providers.api_anthropic import AnthropicApiProvider
from app.providers.api_openai import OpenAiApiProvider
from app.providers.cli_claude import ClaudeCliProvider
from app.providers.cli_codex import CodexCliProvider
from app.providers.factory import build_provider
from app.repositories.config_repository import AgentConfig


def test_build_provider_returns_claude_cli_provider(tmp_path: Path):
    config = AgentConfig(strategy="cli", provider="claude")
    assert isinstance(build_provider(config, tmp_path), ClaudeCliProvider)


def test_build_provider_returns_codex_cli_provider(tmp_path: Path):
    config = AgentConfig(strategy="cli", provider="codex")
    assert isinstance(build_provider(config, tmp_path), CodexCliProvider)


def test_build_provider_returns_anthropic_api_provider(tmp_path: Path):
    config = AgentConfig(strategy="api-key", provider="anthropic", api_key="sk-test")
    assert isinstance(build_provider(config, tmp_path), AnthropicApiProvider)


def test_build_provider_returns_openai_api_provider(tmp_path: Path):
    config = AgentConfig(strategy="api-key", provider="openai", api_key="sk-test")
    assert isinstance(build_provider(config, tmp_path), OpenAiApiProvider)
