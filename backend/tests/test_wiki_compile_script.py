import json
from pathlib import Path

from app.graph_store.store import graph_db_path, init_db
from scripts.wiki_compile import main


def test_main_returns_zero_and_prints_summary_json(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({
        "strategy": "api-key", "provider": "anthropic", "api_key": "test-key",
    }))
    init_db(graph_db_path(tmp_path))

    exit_code = main()

    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"pages_updated": 0, "pages_new": 0, "orphans_flagged": 0, "errors": []}


def test_main_returns_one_without_config(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    exit_code = main()
    assert exit_code == 1
