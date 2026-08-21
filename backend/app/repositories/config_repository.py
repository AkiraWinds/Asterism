import json
import os
import tempfile
from dataclasses import dataclass, field
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
    # repr=False so logging/printing an AgentConfig (e.g. `logger.info("%s", config)`)
    # can never leak the key by accident (SANYI.md's credential-handling invariant).
    api_key: str | None = field(default=None, repr=False)


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


FONT_SCALE_MIN = 0.85
FONT_SCALE_MAX = 1.3
FONT_SCALE_DEFAULT = 1.0


def load_font_scale(data_root: Path) -> float:
    """UI display preference, independent of provider config — same loosely
    read precedent as load_brave_api_key: a missing file, invalid JSON, or
    missing/malformed field all fall back to the default rather than
    raising, since this must never block the app from rendering. A value
    outside the valid range (e.g. a hand-edited config.json) is clamped
    rather than rejected, for the same reason.
    """
    config_path = data_root / "config.json"
    if not config_path.exists():
        return FONT_SCALE_DEFAULT

    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return FONT_SCALE_DEFAULT

    value = data.get("font_scale")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return FONT_SCALE_DEFAULT

    return min(max(float(value), FONT_SCALE_MIN), FONT_SCALE_MAX)


def save_font_scale(data_root: Path, value: float) -> None:
    """Read-modify-write: preserves every other config.json field (provider
    strategy/keys included) untouched, the same shape as any other
    single-field config update. Unlike load_font_scale, an out-of-range
    write is rejected outright rather than silently clamped, so a caller
    gets an explicit error instead of a silently-different saved value.

    Unlike the read-path helpers above, a write must never silently paper
    over a malformed config.json: resetting to `{}` here would destroy
    'strategy'/'provider'/'api_key'/'embeddings_api_key'/'brave_api_key' with
    no signal to the caller. So unparseable or non-dict JSON raises
    ConfigError instead (the /preferences router maps this to a 400),
    refusing to save rather than clobbering the file. The write itself is
    also atomic (temp file + os.replace) so a crash/interruption mid-write
    can't leave config.json truncated for the rest of the app to trip over.
    """
    if not (FONT_SCALE_MIN <= value <= FONT_SCALE_MAX):
        raise ConfigError(f"font_scale must be between {FONT_SCALE_MIN} and {FONT_SCALE_MAX}, got {value!r}")

    config_path = data_root / "config.json"
    data_root.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config.json is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"config.json must contain a JSON object, got {type(data).__name__}")

    data["font_scale"] = value

    fd, tmp_path = tempfile.mkstemp(dir=data_root, prefix=".config.json.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data, indent=2))
        os.replace(tmp_path, config_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
