import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_preferences_returns_default_when_config_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.get("/preferences")

    assert response.status_code == 200
    assert response.json() == {"font_scale": 1.0}


def test_get_preferences_returns_stored_value(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps({"strategy": "cli", "provider": "claude", "font_scale": 1.15}))

    response = client.get("/preferences")

    assert response.status_code == 200
    assert response.json() == {"font_scale": 1.15}


def test_put_preferences_saves_value(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps({"strategy": "cli", "provider": "claude"}))

    response = client.put("/preferences", json={"font_scale": 0.925})

    assert response.status_code == 200
    assert response.json() == {"font_scale": 0.925}
    assert json.loads((tmp_path / "config.json").read_text())["font_scale"] == 0.925


def test_put_preferences_rejects_out_of_range_value(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.put("/preferences", json={"font_scale": 5.0})

    assert response.status_code == 400
