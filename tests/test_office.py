"""Virtual Office endpoints, with the crew stubbed out (no model calls)."""

import time

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def _wait(job_id, status, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f"/office/jobs/{job_id}").json()
        if state["status"] == status:
            return state
        time.sleep(0.05)
    raise AssertionError(f"job never reached {status}: {state}")


def test_office_page_served():
    resp = client.get("/office")
    assert resp.status_code == 200
    assert "Agent Office" in resp.text


def test_job_runs_records_desks_and_chat_revises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def fake_run(posting, force=False, on_event=None):
        on_event("scout", "working", "Reading...")
        on_event("scout", "done", "Facts extracted.")
        on_event("writer", "done", "Ready.")
        return {"verdict": "RECOMMEND", "forced": False, "fit_output": "",
                "proposal": "TICKETBOT hello", "warnings": []}

    def fake_revise(posting, proposal, instruction, on_event=None):
        return {"proposal": proposal + " (" + instruction + ")", "warnings": []}

    monkeypatch.setattr(api, "run_pipeline", fake_run)
    monkeypatch.setattr(api, "revise_proposal", fake_revise)

    job_id = client.post("/office/jobs", json={"posting": "a job " * 40}).json()["id"]
    state = _wait(job_id, "done")
    assert state["desks"]["scout"] == {"status": "done", "say": "Facts extracted."}
    assert state["result"]["proposal"] == "TICKETBOT hello"
    assert "posting" not in state

    assert client.post(f"/office/jobs/{job_id}/chat", json={"message": "shorter"}).status_code == 200
    deadline = time.time() + 5
    while "(shorter)" not in client.get(f"/office/jobs/{job_id}").json()["result"]["proposal"]:
        assert time.time() < deadline
        time.sleep(0.05)
    chat = client.get(f"/office/jobs/{job_id}").json()["chat"]
    assert {"from": "you", "text": "shorter"} in chat


def test_chat_refused_without_proposal(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(api, "run_pipeline", lambda posting, force=False, on_event=None: {
        "verdict": "SKIP", "forced": False, "fit_output": "", "proposal": "", "warnings": []})
    job_id = client.post("/office/jobs", json={"posting": "a job " * 40}).json()["id"]
    _wait(job_id, "done")
    assert client.post(f"/office/jobs/{job_id}/chat", json={"message": "hi"}).status_code == 409
    assert client.get("/office/jobs/nope").status_code == 404


def test_sample_and_short_posting_guard(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    sample = client.get("/office/sample").json()["posting"]
    assert "TICKETBOT" in sample
    resp = client.post("/office/jobs", json={"posting": "samples\\sample_posting.txt"})
    assert resp.status_code == 422 and "too short" in resp.json()["detail"]
