import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.providers.base import ProviderError, ProviderMissingError, ProviderTimeoutError
from app.providers.cli_claude import ClaudeCliProvider


def test_complete_returns_stdout_on_success():
    provider = ClaudeCliProvider()
    with patch("app.providers.cli_claude.shutil.which", return_value="/usr/local/bin/claude"), \
         patch("app.providers.cli_claude.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Hello back\n", stderr="")

        result = provider.complete("Hello")

    assert result == "Hello back"
    args, kwargs = mock_run.call_args
    assert args[0] == ["/usr/local/bin/claude", "--print", "--tools", "", "--output-format", "text"]
    assert kwargs["input"] == "Hello"
    assert kwargs["timeout"] == 600
    assert "CLAUDECODE" not in kwargs["env"]


def test_complete_raises_missing_when_cli_not_on_path():
    provider = ClaudeCliProvider()
    with patch("app.providers.cli_claude.shutil.which", return_value=None):
        with pytest.raises(ProviderMissingError):
            provider.complete("Hello")


def test_complete_raises_provider_error_on_nonzero_exit():
    provider = ClaudeCliProvider()
    with patch("app.providers.cli_claude.shutil.which", return_value="/usr/local/bin/claude"), \
         patch("app.providers.cli_claude.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")

        with pytest.raises(ProviderError, match="boom"):
            provider.complete("Hello")


def test_complete_raises_timeout_error():
    provider = ClaudeCliProvider()
    with patch("app.providers.cli_claude.shutil.which", return_value="/usr/local/bin/claude"), \
         patch(
             "app.providers.cli_claude.subprocess.run",
             side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=600),
         ):
        with pytest.raises(ProviderTimeoutError):
            provider.complete("Hello")
