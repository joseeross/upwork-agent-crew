"""HTTP wrapper around crew.run_pipeline() so n8n can call the crew.

    uvicorn api:app --host 0.0.0.0 --port 8000

POST /run   {"posting": "<raw job text>", "force": false}
GET  /health

The endpoint is a plain (sync) def on purpose: FastAPI runs it in a worker
thread, so a multi-minute crew run doesn't block /health. There is no auth
layer -- docker-compose.yml keeps this service on the internal network
only, reachable by n8n and nothing else. Don't publish its port.
"""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from crew import load_api_key, run_pipeline

load_api_key()

app = FastAPI(title="Upwork Agent Crew")


class RunRequest(BaseModel):
    posting: str
    force: bool = False


@app.get("/health")
def health():
    return {"ok": True, "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/run")
def run(req: RunRequest):
    if not req.posting.strip():
        raise HTTPException(status_code=422, detail="posting is empty")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not set")
    return run_pipeline(req.posting, force=req.force)
