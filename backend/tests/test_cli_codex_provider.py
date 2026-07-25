import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.providers.base import ProviderError, ProviderMissingError, ProviderTimeoutError
from app.providers.cli_codex import CodexCliProvider


def _fake_run_writing_output(response_text: str):
    def _run(args, **kwargs):
        output_index = args.index("--output-last-message") + 1
        Path(args[output_index]).write_text(response_text)
        return MagicMock(returncode=0, stdout="", stderr="")

    return _run


def test_complete_reads_output_last_message_file(tmp_path: Path):
    provider = CodexCliProvider(data_root=tmp_path)
    with patch("app.providers.cli_codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch(
             "app.providers.cli_codex.subprocess.run",
             side_effect=_fake_run_writing_output("Hello back"),
         ) as mock_run:
        result = provider.complete("Hello")

    assert result == "Hello back"
    args = mock_run.call_args[0][0]
    assert args[0] == "/usr/local/bin/codex"
    assert args[1] == "exec"
    assert "--cd" in args and str(tmp_path) in args
    assert "--output-last-message" in args
    assert args[-1] == "-"


def test_complete_raises_missing_when_cli_not_found(tmp_path: Path):
    provider = CodexCliProvider(data_root=tmp_path)
    with patch("app.providers.cli_codex.shutil.which", return_value=None), \
         patch("app.providers.cli_codex.os.access", return_value=False):
        with pytest.raises(ProviderMissingError):
            provider.complete("Hello")


def test_complete_raises_provider_error_on_nonzero_exit(tmp_path: Path):
    provider = CodexCliProvider(data_root=tmp_path)
    with patch("app.providers.cli_codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch("app.providers.cli_codex.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")

        with pytest.raises(ProviderError, match="boom"):
            provider.complete("Hello")


def test_complete_raises_timeout_error(tmp_path: Path):
    provider = CodexCliProvider(data_root=tmp_path)
    with patch("app.providers.cli_codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch(
             "app.providers.cli_codex.subprocess.run",
             side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=600),
         ):
        with pytest.raises(ProviderTimeoutError):
            provider.complete("Hello")


def test_complete_raises_missing_on_file_not_found(tmp_path: Path):
    provider = CodexCliProvider(data_root=tmp_path)
    with patch("app.providers.cli_codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch(
             "app.providers.cli_codex.subprocess.run",
             side_effect=FileNotFoundError("codex not found"),
         ):
        with pytest.raises(ProviderMissingError):
            provider.complete("Hello")


def test_complete_raises_missing_on_oserror(tmp_path: Path):
    provider = CodexCliProvider(data_root=tmp_path)
    with patch("app.providers.cli_codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch(
             "app.providers.cli_codex.subprocess.run",
             side_effect=OSError("Permission denied"),
         ):
        with pytest.raises(ProviderMissingError):
            provider.complete("Hello")
