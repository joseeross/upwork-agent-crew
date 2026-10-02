"""HTTP wrapper tests. run_pipeline is stubbed, so no model calls are made."""

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_health(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert client.get("/health").json() == {"ok": True, "anthropic_key_set": True}


def test_run_rejects_empty_posting(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert client.post("/run", json={"posting": "   "}).status_code == 422


def test_run_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.post("/run", json={"posting": "a job"}).status_code == 503


def test_run_passes_through(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    seen = {}

    def fake_pipeline(posting, force=False):
        seen.update(posting=posting, force=force)
        return {"verdict": "SKIP", "proposal": ""}

    monkeypatch.setattr(api, "run_pipeline", fake_pipeline)
    resp = client.post("/run", json={"posting": "a job", "force": True})
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "SKIP"
    assert seen == {"posting": "a job", "force": True}
