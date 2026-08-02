import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.graph_store.store import get_concept, graph_db_path, init_db, insert_concept
from app.main import app
from app.providers.base import Provider

client = TestClient(app)


# Matches the style of tests/test_watchlist_resolver.py (Task 12): a fixed-response
# stand-in for a real LLM provider so approve()'s "draft a brand-new concept" branch
# doesn't need network access.
class _StubProvider(Provider):
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


def _write_config(data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "config.json").write_text(json.dumps({
        "strategy": "api-key", "provider": "openai", "api_key": "fake", "embeddings_api_key": "fake-embed",
    }))


def test_post_watchlist_creates_and_resolves_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by POST /watchlist) calls its
    # own module-level embed_text reference in app.watchlist.resolver, separate from
    # the router's — both need stubbing to avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    # No graph match and no Brave key configured, so resolution falls through to
    # the LLM-reasoning branch — stub the provider to avoid a real network call.
    monkeypatch.setattr("app.routers.watchlist.build_provider", lambda config, data_root: _StubProvider("A definition."))

    response = client.post("/watchlist", json={"term": "Agentic AI"})

    assert response.status_code == 200
    body = response.json()
    assert body["term"] == "Agentic AI"
    assert body["status"] == "pending"  # not yet approved, but has a draft


def test_get_watchlist_lists_entries(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by POST /watchlist) calls its
    # own module-level embed_text reference in app.watchlist.resolver, separate from
    # the router's — both need stubbing to avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    # No graph match and no Brave key configured, so resolution falls through to
    # the LLM-reasoning branch — stub the provider to avoid a real network call.
    monkeypatch.setattr("app.routers.watchlist.build_provider", lambda config, data_root: _StubProvider("A definition."))
    client.post("/watchlist", json={"term": "Agentic AI"})

    response = client.get("/watchlist")

    assert len(response.json()["entries"]) == 1


def test_delete_watchlist_entry_returns_204_and_keeps_resolved_concept(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "Agentic AI", "def", [0.0, 1.0], False, "2026-08-01T00:00:00Z")
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by POST /watchlist) calls its
    # own module-level embed_text reference in app.watchlist.resolver, separate from
    # the router's — both need stubbing to avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    created = client.post("/watchlist", json={"term": "Agentic AI"}).json()

    response = client.delete(f"/watchlist/{created['id']}")

    assert response.status_code == 204
    assert get_concept(db_path, "c_1") is not None


def test_approve_watchlist_entry_creates_golden_concept_from_draft(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by POST /watchlist) calls its
    # own module-level embed_text reference in app.watchlist.resolver, separate from
    # the router's — both need stubbing to avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    monkeypatch.setattr("app.routers.watchlist.build_provider", lambda config, data_root: _StubProvider("A drafted definition."))
    created = client.post("/watchlist", json={"term": "Some new term"}).json()
    assert created["draft_definition"] == "A drafted definition."

    response = client.post(f"/watchlist/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["resolved_concept_id"] is not None
    concept = get_concept(graph_db_path(tmp_path), body["resolved_concept_id"])
    assert concept["golden"] is True
    assert concept["definition"] == "A drafted definition."


def test_approve_watchlist_entry_flags_matched_concept_golden(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    db_path = graph_db_path(tmp_path)
    init_db(db_path)
    insert_concept(db_path, "c_1", "Agentic AI", "Existing def.", [0.0, 1.0], False, "2026-08-01T00:00:00Z")
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by POST /watchlist) calls its
    # own module-level embed_text reference in app.watchlist.resolver, separate from
    # the router's — both need stubbing to avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    created = client.post("/watchlist", json={"term": "Agentic AI"}).json()
    assert created["draft_matched_concept_id"] == "c_1"

    response = client.post(f"/watchlist/{created['id']}/approve")

    assert response.status_code == 200
    assert response.json()["resolved_concept_id"] == "c_1"
    assert get_concept(db_path, "c_1")["golden"] is True


def test_patch_watchlist_entry_flips_resolved_back_to_pending(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by both POST /watchlist and
    # PATCH /watchlist/{id}) calls its own module-level embed_text reference in
    # app.watchlist.resolver, separate from the router's — both need stubbing to
    # avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    monkeypatch.setattr("app.routers.watchlist.build_provider", lambda config, data_root: _StubProvider("A drafted definition."))
    created = client.post("/watchlist", json={"term": "Some new term"}).json()
    approved = client.post(f"/watchlist/{created['id']}/approve").json()
    assert approved["status"] == "resolved"
    assert approved["resolved_concept_id"] is not None

    response = client.patch(f"/watchlist/{created['id']}", json={"term": "A renamed term"})

    assert response.status_code == 200
    body = response.json()
    assert body["term"] == "A renamed term"
    assert body["status"] == "pending"
    assert body["resolved_concept_id"] is None


def test_approve_watchlist_entry_is_idempotent_and_does_not_orphan_concept(tmp_path: Path, monkeypatch):
    # Whole-branch review finding #4: approving an already-resolved entry a
    # second time must not mint a second golden concept and overwrite
    # resolved_concept_id, which would orphan the first concept in the graph.
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    monkeypatch.setattr("app.routers.watchlist.build_provider", lambda config, data_root: _StubProvider("A drafted definition."))
    created = client.post("/watchlist", json={"term": "Some new term"}).json()

    first = client.post(f"/watchlist/{created['id']}/approve").json()
    second = client.post(f"/watchlist/{created['id']}/approve").json()

    assert first["status"] == "resolved"
    assert second["status"] == "resolved"
    assert second["resolved_concept_id"] == first["resolved_concept_id"]
    from app.graph_store.store import list_concepts
    assert len(list_concepts(graph_db_path(tmp_path))) == 1


def test_reject_watchlist_entry_marks_rejected_without_creating_concept(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTERISM_DATA_ROOT", str(tmp_path))
    _write_config(tmp_path)
    monkeypatch.setattr("app.routers.watchlist.embed_text", lambda api_key, text: [0.0, 1.0])
    # resolve_watchlist_entry (invoked synchronously by POST /watchlist) calls its
    # own module-level embed_text reference in app.watchlist.resolver, separate from
    # the router's — both need stubbing to avoid a real embeddings API call.
    monkeypatch.setattr("app.watchlist.resolver.embed_text", lambda api_key, text: [0.0, 1.0])
    monkeypatch.setattr("app.routers.watchlist.build_provider", lambda config, data_root: _StubProvider("Drafted."))
    created = client.post("/watchlist", json={"term": "Some new term"}).json()

    response = client.post(f"/watchlist/{created['id']}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["resolved_concept_id"] is None
