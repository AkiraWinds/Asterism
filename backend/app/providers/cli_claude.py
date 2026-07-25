import os
import shutil
import subprocess

from app.providers.base import Provider, ProviderError, ProviderMissingError, ProviderTimeoutError

TIMEOUT_SECONDS = 600


class ClaudeCliProvider(Provider):
    def __init__(self, command: str = "claude"):
        self._command = command

    def complete(self, prompt: str) -> str:
        resolved = shutil.which(self._command)
        if resolved is None:
            raise ProviderMissingError(
                "Claude CLI not found on PATH. Install it with 'npm install -g @anthropic-ai/claude-code'."
            )

        env = {key: value for key, value in os.environ.items() if key != "CLAUDECODE"}
        args = [resolved, "--print", "--tools", "", "--output-format", "text"]

        try:
            result = subprocess.run(
                args,
                input=prompt,
                capture_output=True,
                text=True,
                env=env,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderTimeoutError(f"Claude CLI timed out after {TIMEOUT_SECONDS}s") from exc

        if result.returncode != 0:
            message = result.stderr.strip() or f"Claude CLI exited with code {result.returncode}"
            raise ProviderError(message)

        return result.stdout.strip()
