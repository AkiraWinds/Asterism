import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.providers.base import Provider, ProviderError, ProviderMissingError, ProviderTimeoutError

TIMEOUT_SECONDS = 600
FALLBACK_COMMAND_PATHS = ["/Applications/Codex.app/Contents/Resources/codex"]


def _resolve_command(command: str) -> str | None:
    resolved = shutil.which(command)
    if resolved is not None:
        return resolved
    for fallback in FALLBACK_COMMAND_PATHS:
        if os.access(fallback, os.X_OK):
            return fallback
    return None


class CodexCliProvider(Provider):
    def __init__(self, data_root: Path, command: str = "codex"):
        self._data_root = data_root
        self._command = command

    def complete(self, prompt: str) -> str:
        resolved = _resolve_command(self._command)
        if resolved is None:
            raise ProviderMissingError(
                "Codex CLI not found on PATH. Install it with 'npm install -g @openai/codex'."
            )

        with tempfile.TemporaryDirectory(prefix="asterism-codex-") as tmp_dir:
            output_path = Path(tmp_dir) / "last-message.txt"
            args = [
                resolved,
                "exec",
                "--cd", str(self._data_root),
                "--sandbox", "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "--color", "never",
                "--output-last-message", str(output_path),
                "-",
            ]

            try:
                result = subprocess.run(
                    args,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderTimeoutError(f"Codex CLI timed out after {TIMEOUT_SECONDS}s") from exc
            except (FileNotFoundError, OSError) as exc:
                raise ProviderMissingError(
                    "Codex CLI not found on PATH. Install it with 'npm install -g @openai/codex'."
                ) from exc

            if result.returncode != 0:
                message = result.stderr.strip() or f"Codex CLI exited with code {result.returncode}"
                raise ProviderError(message)

            if output_path.exists():
                return output_path.read_text().strip()
            return result.stdout.strip()
