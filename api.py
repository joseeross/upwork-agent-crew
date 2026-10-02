"""HTTP wrapper around the crew: the n8n endpoint plus the Virtual Office.

    uvicorn api:app --host 0.0.0.0 --port 8000

n8n:
  POST /run   {"posting": "<raw job text>", "force": false}
  GET  /health

Virtual Office (open http://localhost:8000/office in a browser):
  GET  /office                    the page
  POST /office/jobs               {"posting", "force"} -> {"id"}; runs in background
  GET  /office/jobs/{id}          live state: agent desks, activity log, result, chat
  POST /office/jobs/{id}/chat     {"message"} -> Proposal Writer revises the draft

/run is a plain (sync) def on purpose: FastAPI runs it in a worker thread,
so a multi-minute crew run doesn't block /health. There is no auth layer:
docker-compose.yml publishes this port on 127.0.0.1 only, so it is
reachable from this computer and the n8n container, nothing else.
"""

import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from crew import load_api_key, revise_proposal, run_pipeline

load_api_key()

app = FastAPI(title="Upwork Agent Crew")

OFFICE_HTML = Path(__file__).resolve().parent / "office" / "index.html"
AGENTS = ("scout", "fit", "research", "writer")
MAX_LOG = 200

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class RunRequest(BaseModel):
    posting: str
    force: bool = False


class ChatRequest(BaseModel):
    message: str


def _require_ready(posting: str) -> None:
    if not posting.strip():
        raise HTTPException(status_code=422, detail="posting is empty")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not set")


@app.get("/health")
def health():
    return {"ok": True, "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/run")
def run(req: RunRequest):
    _require_ready(req.posting)
    return run_pipeline(req.posting, force=req.force)


# ---------------------------------------------------------------- office

def _event_recorder(job_id: str):
    def on_event(agent: str, status: str, text: str = "") -> None:
        with _lock:
            job = _jobs[job_id]
            desk = job["desks"].get(agent)
            if desk is not None:
                if status in ("working", "done"):
                    desk["status"] = status
                if text:
                    desk["say"] = text
            job["log"].append({"t": time.time(), "agent": agent, "status": status, "text": text})
            del job["log"][:-MAX_LOG]
    return on_event


def _run_job(job_id: str) -> None:
    job = _jobs[job_id]
    try:
        result = run_pipeline(job["posting"], force=job["force"], on_event=_event_recorder(job_id))
        with _lock:
            job["result"] = result
            job["status"] = "done"
            if not result["proposal"]:
                job["chat"].append({
                    "from": "writer",
                    "text": "The Fit Analyst said SKIP, so I didn't draft anything. "
                            "Start again with \"Draft anyway\" ticked if you disagree.",
                })
            else:
                job["chat"].append({
                    "from": "writer",
                    "text": "Draft's ready. Tell me what to change: shorter, a different "
                            "rate, more about your n8n work... I'll only use facts from your profile.",
                })
    except Exception as e:  # surface failures on the page instead of hanging
        with _lock:
            job["status"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"


def _run_revision(job_id: str, message: str) -> None:
    job = _jobs[job_id]
    try:
        revised = revise_proposal(
            job["posting"], job["result"]["proposal"], message, on_event=_event_recorder(job_id)
        )
        with _lock:
            job["result"].update(revised)
            job["status"] = "done"
            job["chat"].append({"from": "writer", "text": "Done. The updated proposal is above."})
    except Exception as e:
        with _lock:
            job["status"] = "done"
            job["chat"].append({"from": "writer", "text": f"Sorry, that revision failed: {type(e).__name__}: {e}"})


@app.get("/office")
def office():
    return FileResponse(OFFICE_HTML)


@app.post("/office/jobs")
def office_start(req: RunRequest):
    _require_ready(req.posting)
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "running",
            "posting": req.posting,
            "force": req.force,
            "desks": {a: {"status": "idle", "say": ""} for a in AGENTS},
            "log": [],
            "chat": [],
            "result": None,
            "error": None,
        }
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"id": job_id}


@app.get("/office/jobs/{job_id}")
def office_state(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        return {k: v for k, v in job.items() if k != "posting"}


@app.post("/office/jobs/{job_id}/chat")
def office_chat(job_id: str, req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is empty")
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        if job["status"] != "done" or not (job["result"] or {}).get("proposal"):
            raise HTTPException(status_code=409, detail="no finished proposal to revise yet")
        job["status"] = "revising"
        job["chat"].append({"from": "you", "text": message})
    threading.Thread(target=_run_revision, args=(job_id, message), daemon=True).start()
    return {"ok": True}
