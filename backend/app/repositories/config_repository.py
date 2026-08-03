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


def load_embeddings_api_key(data_root: Path) -> str:
    """Load the OpenAI embeddings API key, independent of the chat/completion
    provider's strategy/provider/api_key fields (Anthropic has no embeddings
    endpoint and CLI providers have no embedding capability at all, so this
    is a separate, always-required key for the concept graph feature).
    """
    config_path = data_root / "config.json"
    if not config_path.exists():
        raise ConfigError(
            f"config.json not found at {config_path}. Set 'embeddings_api_key' for the concept graph feature."
        )

    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json is not valid JSON: {exc}") from exc

    api_key = data.get("embeddings_api_key")
    if not api_key:
        raise ConfigError("config.json must set 'embeddings_api_key' for the concept graph feature")

    return api_key


def load_brave_api_key(data_root: Path) -> str | None:
    """Optional — unlike load_config/load_embeddings_api_key, a missing key
    here is not an error: it means the extraction/watchlist resolution chain
    skips the web-search step and falls straight through to LLM reasoning
    (see design doc's Resolution chain), the same optional-key precedent the
    Brave-backed feed feature already established (todo.md's Known Risks).
    """
    config_path = data_root / "config.json"
    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return None
    return data.get("brave_api_key") or None


def load_authenticated_hosts(data_root: Path) -> dict[str, str]:
    """Optional per-host Cookie-header map for fetching content behind a login wall
    using the user's own session (e.g. a paid Medium membership). Disk-only — never
    exposed via API/UI, since a session cookie logs in as the user. Missing file or
    missing field both mean "no authenticated hosts configured", not an error.
    """
    config_path = data_root / "config.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return {}
    return data.get("authenticated_hosts") or {}
