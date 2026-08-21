import json
from pathlib import Path

import pytest

from app.repositories.config_repository import (
    AgentConfig,
    ConfigError,
    load_config,
    load_embeddings_api_key,
    load_brave_api_key,
    load_font_scale,
    save_font_scale,
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


def test_load_font_scale_returns_default_when_config_missing(tmp_path: Path):
    assert load_font_scale(tmp_path) == 1.0


def test_load_font_scale_returns_default_when_field_absent(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "claude"})
    assert load_font_scale(tmp_path) == 1.0


def test_load_font_scale_returns_value_when_set(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "claude", "font_scale": 1.15})
    assert load_font_scale(tmp_path) == 1.15


def test_load_font_scale_clamps_value_above_max(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "claude", "font_scale": 5.0})
    assert load_font_scale(tmp_path) == 1.3


def test_load_font_scale_clamps_value_below_min(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "claude", "font_scale": 0.1})
    assert load_font_scale(tmp_path) == 0.85


def test_save_font_scale_raises_on_out_of_range_value(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "cli", "provider": "claude"})
    with pytest.raises(ConfigError):
        save_font_scale(tmp_path, 2.0)


def test_save_font_scale_writes_value_and_preserves_other_fields(tmp_path: Path):
    _write_config(tmp_path, {"strategy": "api-key", "provider": "anthropic", "api_key": "sk-test"})

    save_font_scale(tmp_path, 1.15)

    data = json.loads((tmp_path / "config.json").read_text())
    assert data["font_scale"] == 1.15
    assert data["strategy"] == "api-key"
    assert data["provider"] == "anthropic"
    assert data["api_key"] == "sk-test"


def test_save_font_scale_creates_config_when_missing(tmp_path: Path):
    save_font_scale(tmp_path, 0.925)

    data = json.loads((tmp_path / "config.json").read_text())
    assert data["font_scale"] == 0.925


def test_save_font_scale_raises_on_invalid_json_instead_of_clobbering(tmp_path: Path):
    # Regression: previously this silently reset config.json to `{}` before
    # writing, destroying strategy/provider/api_key/etc with no error raised.
    tmp_path.mkdir(parents=True, exist_ok=True)
    original = "{not valid json"
    (tmp_path / "config.json").write_text(original)

    with pytest.raises(ConfigError):
        save_font_scale(tmp_path, 1.15)

    # File must be left untouched, not clobbered.
    assert (tmp_path / "config.json").read_text() == original


def test_save_font_scale_raises_when_config_is_not_a_dict(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps([1, 2, 3]))

    with pytest.raises(ConfigError):
        save_font_scale(tmp_path, 1.15)
