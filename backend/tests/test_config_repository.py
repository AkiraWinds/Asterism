import json
from pathlib import Path

import pytest

from app.repositories.config_repository import (
    AgentConfig,
    ConfigError,
    load_config,
    load_embeddings_api_key,
    load_brave_api_key,
)


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


def test_load_embeddings_api_key_returns_key(tmp_path: Path):
    (tmp_path / "config.json").write_text(
        json.dumps({"strategy": "api-key", "provider": "anthropic", "api_key": "fake", "embeddings_api_key": "sk-embed"})
    )
    assert load_embeddings_api_key(tmp_path) == "sk-embed"


def test_load_embeddings_api_key_raises_when_config_missing(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_embeddings_api_key(tmp_path)


def test_load_embeddings_api_key_raises_when_field_missing(tmp_path: Path):
    (tmp_path / "config.json").write_text(json.dumps({"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}))
    with pytest.raises(ConfigError):
        load_embeddings_api_key(tmp_path)


def test_load_brave_api_key_returns_none_when_config_missing(tmp_path: Path):
    assert load_brave_api_key(tmp_path) is None


def test_load_brave_api_key_returns_none_when_field_unset(tmp_path: Path):
    (tmp_path / "config.json").write_text(json.dumps({"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}))
    assert load_brave_api_key(tmp_path) is None


def test_load_brave_api_key_returns_key_when_set(tmp_path: Path):
    (tmp_path / "config.json").write_text(
        json.dumps({"strategy": "api-key", "provider": "anthropic", "api_key": "fake", "brave_api_key": "brave-key"})
    )
    assert load_brave_api_key(tmp_path) == "brave-key"


def test_agent_config_repr_never_includes_the_api_key():
    # SANYI.md Buyi: credential handling — api_key must never be written to
    # logs/debug output. logger.info("%s", config) (or any bare print/repr)
    # must not leak it, so the dataclass field is repr=False.
    config = AgentConfig(strategy="api-key", provider="anthropic", api_key="sk-super-secret")

    assert "sk-super-secret" not in repr(config)
