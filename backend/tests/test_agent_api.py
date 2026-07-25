from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    ProviderMissingError,
    ProviderTimeoutError,
)

client = TestClient(app)


class FakeProvider(Provider):
    def __init__(self, result: str | None = None, error: Exception | None = None):
        self._result = result
        self._error = error

    def complete(self, prompt: str) -> str:
        if self._error:
            raise self._error
        return self._result


def _write_valid_config(data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "config.json").write_text('{"strategy": "cli", "provider": "claude"}')


def test_complete_returns_response_on_success(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_valid_config(tmp_path)
    monkeypatch.setattr(
        "app.routers.agent.build_provider",
        lambda config, data_root: FakeProvider(result="Hi there"),
    )

    response = client.post("/agent/complete", json={"prompt": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"response": "Hi there"}


def test_complete_returns_400_when_config_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/agent/complete", json={"prompt": "Hello"})

    assert response.status_code == 400
    assert response.json()["error_type"] == "config"


@pytest.mark.parametrize(
    "error, expected_status, expected_error_type",
    [
        (ProviderMissingError("not found"), 400, "missing"),
        (ProviderConfigError("bad key"), 400, "config"),
        (ProviderTimeoutError("timed out"), 504, "timeout"),
        (ProviderError("boom"), 502, "error"),
    ],
)
def test_complete_maps_provider_errors_to_http_status(
    tmp_path: Path, monkeypatch, error, expected_status, expected_error_type
):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_valid_config(tmp_path)
    monkeypatch.setattr(
        "app.routers.agent.build_provider",
        lambda config, data_root: FakeProvider(error=error),
    )

    response = client.post("/agent/complete", json={"prompt": "Hello"})

    assert response.status_code == expected_status
    assert response.json()["error_type"] == expected_error_type
