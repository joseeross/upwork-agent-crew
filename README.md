# Upwork Agent Crew

A real [CrewAI](https://github.com/crewAIInc/crewAI) crew that triages Upwork
job postings and drafts tailored proposals for Jose Ross (AI Engineer &
Automation Specialist). Built as both a working tool and a portfolio piece.

## What it does

Two-stage pipeline:

**Stage 1 -- Job Scout -> Fit Analyst** (one Crew run)
- `Job Scout` parses a raw job posting into structured fields (rate, hours,
  duration, hard requirements, screening questions) using a deterministic
  regex tool (`ParseJobPostingTool`) -- no LLM guessing on numbers.
- `Fit Analyst` loads Jose's real profile from `config/profile.yaml` and
  scores the job honestly: stack match, rate match, client signals, and any
  real gap (e.g. "wants deployed client results, portfolio is strong
  self-directed work") named explicitly, not smoothed over. Ends with a
  parseable `VERDICT: RECOMMEND` or `VERDICT: SKIP` line.

**Gate:** Stage 2 only runs if the verdict is `RECOMMEND`, or you pass
`--force`.

**Stage 2 -- Client Researcher -> Proposal Writer** (a second Crew run)
- `Client Researcher` looks up the hiring client/company if named, via
  Serper. If no `SERPER_API_KEY` is set, it says so plainly instead of
  inventing a client background.
- `Proposal Writer` (deliberately given no tools) drafts the proposal: leads
  with real past work, answers every screening question, includes any
  required exact phrase verbatim, and addresses any flagged gap honestly
  instead of implying proof that doesn't exist.

## Design choices worth knowing about

- **Tools are scoped per-agent on purpose.** The Proposal Writer has no
  search tool, so it can't call something "research" that it invented.
- **Hard facts (rate, hours, screening phrases) are extracted with regex,
  not an LLM**, to remove hallucination risk on numbers that matter.
- **Two separate `Crew` instances, not one.** CrewAI's sequential `Process`
  has no built-in branching, so conditional "only draft a proposal if the
  job is worth it" logic is done in `crew.py` between two crew runs, with
  Stage 1's results passed into Stage 2 as plain text.
- **No fabricated research.** If there's no client name or no search key,
  the researcher says so instead of guessing -- same principle applied
  throughout this project's development.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY (required)
# SERPER_API_KEY is optional -- without it, client research is skipped
# honestly rather than faked
```

Edit `config/profile.yaml` as your rate, stack, or preferences change --
it's the single source of truth the Fit Analyst reads, not something
hardcoded into a prompt.

## Run it

```bash
python crew.py path/to/posting.txt
# or, to draft a proposal even on a SKIP verdict:
python crew.py path/to/posting.txt --force
```

A sample posting lives in `samples/sample_posting.txt`. Tests (no API key
needed): `pip install -r requirements-dev.txt && python -m pytest`.

## Run it from n8n

`api.py` exposes the same pipeline over HTTP (`POST /run`), and
`n8n/workflows/upwork-crew.json` is a ready-to-import workflow:

```
Form (paste posting) ─┐
                      ├─> Normalize ─> Run Crew (POST crew-api:8000/run) ─> Proposal drafted?
Webhook POST ─────────┘                                                      ├─ yes -> Gmail draft: proposal + fit + research
                                                                             └─ no  -> Gmail draft: [SKIP] + fit analysis
```

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY
docker compose up -d --build  # n8n on http://localhost:5678, crew-api internal only
```

In n8n: **Workflows → Import from File** → `n8n/workflows/upwork-crew.json`,
attach a Gmail OAuth2 credential to both Gmail nodes, then activate.

- **Form:** open the *Paste Job Posting* node's production URL, paste, submit.
- **Webhook:** `curl -X POST http://localhost:5678/webhook/upwork-job -H 'Content-Type: application/json' -d '{"posting":"...","force":false}'`

Nothing is sent automatically. Every result lands as a Gmail **draft** for
you to review. A crew run takes minutes, so the HTTP node's timeout is set
to 15 min. Upwork dropped its public job RSS feeds in 2024, so intake is by
paste or webhook (for example from a browser extension or an email parser).

## A note on how this was built

This repo was written inside a sandboxed agent session that could not
install new pip packages (no network access to PyPI beyond what's already
vendored) and had no live Anthropic API key available to it. That means
`crewai` itself was never actually executed during development -- every
file was hand-written and syntax-checked (`python -m py_compile`), not
run end-to-end.

What that means for you: install the requirements and run it with your own
key, as above -- that's the first time this pipeline will actually execute.
If something doesn't run cleanly, it's a real bug to fix, not a known gap
I glossed over. I disclosed this rather than quietly shipping it as
"tested."
