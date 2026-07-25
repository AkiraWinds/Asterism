import json
from dataclasses import dataclass
from pathlib import Path

CLI_PROVIDERS = {"claude", "codex"}
API_KEY_PROVIDERS = {"anthropic", "openai"}
STRATEGIES = {"cli", "api-key"}


class ConfigError(ValueError):
    pass


@dataclass
class AgentConfig:
    strategy: str
    provider: str
    api_key: str | None = None


def load_config(data_root: Path) -> AgentConfig:
    config_path = data_root / "config.json"
    if not config_path.exists():
        raise ConfigError(
            f"config.json not found at {config_path}. Create it with a 'strategy' and 'provider' set."
        )

    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json is not valid JSON: {exc}") from exc

    strategy = data.get("strategy")
    provider = data.get("provider")
    api_key = data.get("api_key")

    if strategy not in STRATEGIES:
        raise ConfigError(f"config.json 'strategy' must be one of {sorted(STRATEGIES)}, got {strategy!r}")

    if strategy == "cli" and provider not in CLI_PROVIDERS:
        raise ConfigError(
            f"config.json 'provider' must be one of {sorted(CLI_PROVIDERS)} for strategy 'cli', got {provider!r}"
        )

    if strategy == "api-key":
        if provider not in API_KEY_PROVIDERS:
            raise ConfigError(
                f"config.json 'provider' must be one of {sorted(API_KEY_PROVIDERS)} for strategy 'api-key', got {provider!r}"
            )
        if not api_key:
            raise ConfigError("config.json must set 'api_key' when strategy is 'api-key'")

    return AgentConfig(strategy=strategy, provider=provider, api_key=api_key)
