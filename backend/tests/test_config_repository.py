import json
from pathlib import Path

import pytest

from app.repositories.config_repository import AgentConfig, ConfigError, load_config


def _write_config(data_root: Path, data: dict) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "config.json").write_text(json.dumps(data))


def test_load_config_raises_when_file_missing(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_raises_on_invalid_json(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text("{not valid json")

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_raises_on_unknown_strategy(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "carrier-pigeon", "provider": "claude"})

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_raises_when_cli_provider_invalid(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "anthropic"})

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_raises_when_api_key_strategy_missing_key(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "api-key", "provider": "anthropic"})

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_returns_config_for_valid_cli_strategy(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "codex"})

    config = load_config(tmp_path)

    assert config == AgentConfig(strategy="cli", provider="codex", api_key=None)


def test_load_config_returns_config_for_valid_api_key_strategy(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "api-key", "provider": "openai", "api_key": "sk-test"})

    config = load_config(tmp_path)

    assert config == AgentConfig(strategy="api-key", provider="openai", api_key="sk-test")
