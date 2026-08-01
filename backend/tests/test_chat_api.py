import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import ProviderError, ProviderMissingError

client = TestClient(app)


def _create_source() -> str:
    response = client.post("/sources", json={"title": "Test", "content": "Some content."})
    return response.json()["id"]


def _write_valid_config(data_root: Path) -> None:
    (data_root / "config.json").write_text('{"strategy": "api-key", "provider": "anthropic", "api_key": "fake"}')


def _parse_sse(raw_text: str) -> list[dict]:
    """Parse `event: X\\ndata: Y\\n\\n` frames into [{"event": X or "message", "data": <parsed Y>}, ...]."""
    frames = []
    for block in raw_text.strip().split("\n\n"):
        event = "message"
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if data is not None:
            frames.append({"event": event, "data": data})
    return frames


def test_get_chat_returns_empty_history_when_no_chat_yet(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.get(f"/sources/{source_id}/chat")

    assert response.status_code == 200
    assert response.json()["turns"] == []


def test_post_chat_streams_chunks_and_persists_turns(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_valid_config(tmp_path)
    source_id = _create_source()

    provider = MagicMock()
    provider.stream_complete.return_value = iter(["Hel", "lo"])
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)

    response = client.post(f"/sources/{source_id}/chat", json={"message": "Hi"})

    assert response.status_code == 200
    frames = _parse_sse(response.text)
    assert [f["data"]["text"] for f in frames if f["event"] == "message"] == ["Hel", "lo"]
    assert frames[-1]["event"] == "done"

    history = client.get(f"/sources/{source_id}/chat").json()
    assert [t["role"] for t in history["turns"]] == ["user", "assistant"]
    assert history["turns"][0]["content"] == "Hi"
    assert history["turns"][1]["content"] == "Hello"
    assert history["turns"][1]["truncated"] is False


def test_post_chat_persists_truncated_turn_on_mid_stream_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_valid_config(tmp_path)
    source_id = _create_source()

    def _failing_stream(prompt):
        yield "Par"
        raise ProviderError("connection dropped")

    provider = MagicMock()
    provider.stream_complete.side_effect = _failing_stream
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)

    response = client.post(f"/sources/{source_id}/chat", json={"message": "Hi"})

    assert response.status_code == 200
    frames = _parse_sse(response.text)
    assert frames[-1]["event"] == "error"
    assert frames[-1]["data"]["message"] == "connection dropped"

    history = client.get(f"/sources/{source_id}/chat").json()
    assert history["turns"][1]["truncated"] is True
    assert history["turns"][1]["content"] == "Par"


def test_post_chat_error_on_very_first_chunk_still_persists_empty_truncated_turn(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_valid_config(tmp_path)
    source_id = _create_source()

    def _failing_stream(prompt):
        raise ProviderMissingError("CLI not found")
        yield  # pragma: no cover - unreachable, makes this a generator function

    provider = MagicMock()
    provider.stream_complete.side_effect = _failing_stream
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)

    response = client.post(f"/sources/{source_id}/chat", json={"message": "Hi"})

    assert response.status_code == 200
    frames = _parse_sse(response.text)
    assert frames == [{"event": "error", "data": {"message": "CLI not found"}}]

    history = client.get(f"/sources/{source_id}/chat").json()
    assert history["turns"][1]["truncated"] is True
    assert history["turns"][1]["content"] == ""


def test_post_chat_returns_400_when_config_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.post(f"/sources/{source_id}/chat", json={"message": "Hi"})

    assert response.status_code == 400
    assert response.json()["error_type"] == "config"


def test_post_chat_404_for_unknown_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))

    response = client.post("/sources/does-not-exist/chat", json={"message": "Hi"})

    assert response.status_code == 404


def test_list_conversations_auto_creates_one_for_a_fresh_source(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.get(f"/sources/{source_id}/chats")

    assert response.status_code == 200
    conversations = response.json()
    assert len(conversations) == 1
    assert conversations[0]["title"] == "Chat 1"
    assert conversations[0]["turn_count"] == 0


def test_create_conversation_adds_a_second_thread(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()
    client.get(f"/sources/{source_id}/chats")  # establishes the auto-created "Chat 1"

    created = client.post(f"/sources/{source_id}/chats").json()
    assert created["title"] == "Chat 2"

    listed = client.get(f"/sources/{source_id}/chats").json()
    assert {c["title"] for c in listed} == {"Chat 1", "Chat 2"}


def test_chat_messages_are_isolated_per_conversation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_valid_config(tmp_path)
    source_id = _create_source()

    provider = MagicMock()
    provider.stream_complete.return_value = iter(["hi"])
    monkeypatch.setattr("app.routers.sources.build_provider", lambda config, data_root: provider)

    conv_a = client.get(f"/sources/{source_id}/chats").json()[0]["id"]
    conv_b = client.post(f"/sources/{source_id}/chats").json()["id"]

    client.post(f"/sources/{source_id}/chat?conversation_id={conv_a}", json={"message": "In A"})

    history_a = client.get(f"/sources/{source_id}/chat?conversation_id={conv_a}").json()
    history_b = client.get(f"/sources/{source_id}/chat?conversation_id={conv_b}").json()

    assert [t["content"] for t in history_a["turns"]] == ["In A", "hi"]
    assert history_b["turns"] == []


def test_delete_conversation_removes_it_when_others_remain(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()
    conv_a = client.get(f"/sources/{source_id}/chats").json()[0]["id"]
    conv_b = client.post(f"/sources/{source_id}/chats").json()["id"]

    response = client.delete(f"/sources/{source_id}/chats/{conv_a}")

    assert response.status_code == 200
    assert response.json()["replacement"] is None
    remaining = client.get(f"/sources/{source_id}/chats").json()
    assert [c["id"] for c in remaining] == [conv_b]


def test_delete_last_conversation_creates_a_replacement(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()
    only_conv = client.get(f"/sources/{source_id}/chats").json()[0]["id"]

    response = client.delete(f"/sources/{source_id}/chats/{only_conv}")

    assert response.status_code == 200
    replacement = response.json()["replacement"]
    assert replacement is not None
    assert replacement["id"] != only_conv

    remaining = client.get(f"/sources/{source_id}/chats").json()
    assert [c["id"] for c in remaining] == [replacement["id"]]


def test_delete_unknown_conversation_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    response = client.delete(f"/sources/{source_id}/chats/does-not-exist")

    assert response.status_code == 404


def test_legacy_chat_json_is_migrated_into_a_conversation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    source_id = _create_source()

    legacy_path = tmp_path / "library" / source_id / "chat.json"
    legacy_path.write_text(json.dumps({
        "turns": [
            {"role": "user", "content": "Old message", "attached_highlight": None,
             "truncated": False, "created_at": "2026-01-01T00:00:00+00:00"},
        ]
    }))

    conversations = client.get(f"/sources/{source_id}/chats").json()

    assert len(conversations) == 1
    assert conversations[0]["turn_count"] == 1
    assert not legacy_path.exists()

    history = client.get(f"/sources/{source_id}/chat?conversation_id={conversations[0]['id']}").json()
    assert history["turns"][0]["content"] == "Old message"
