"""Entrypoint: run the Upwork crew against a job posting.

Usage:
    python crew.py path/to/posting.txt
    python crew.py path/to/posting.txt --force   # run proposal stage even on SKIP

Flow:
    Stage 1 (one Crew): Job Scout -> Fit Analyst. Fit Analyst ends its
    output with "VERDICT: RECOMMEND" or "VERDICT: SKIP".
    Gate: if RECOMMEND (or --force passed), run Stage 2.
    Stage 2 (a second Crew): Client Researcher -> Proposal Writer.

Requires ANTHROPIC_API_KEY set (see .env.example). Nothing here runs
without a real crewai install and a real API key -- there is no local
fallback baked into this file on purpose, so what you see locally is
exactly what will happen wherever you actually run this.
"""

import os
import sys

from dotenv import load_dotenv
from crewai import Crew, Process, LLM

from agents.crew_agents import (
    build_job_scout,
    build_fit_analyst,
    build_client_researcher,
    build_proposal_writer,
)
from tasks.crew_tasks import (
    build_scout_task,
    build_fit_task,
    build_research_task,
    build_proposal_task,
)


def parse_verdict(fit_output_text: str) -> str:
    """Pull RECOMMEND/SKIP off the Fit Analyst's final line.

    Defensive: if the model didn't follow the format exactly, default to
    SKIP rather than silently proceeding to draft a proposal for a job
    nobody actually recommended.
    """
    for line in reversed(fit_output_text.strip().splitlines()):
        line = line.strip()
        if line.upper().startswith("VERDICT:"):
            return "RECOMMEND" if "RECOMMEND" in line.upper() else "SKIP"
    return "SKIP"


def main():
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python crew.py path/to/posting.txt [--force]")
        sys.exit(1)

    posting_path = sys.argv[1]
    force = "--force" in sys.argv[2:]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
            "add your key -- this crew makes real model calls and has no "
            "offline fallback."
        )
        sys.exit(1)

    with open(posting_path, "r", encoding="utf-8") as f:
        job_posting_text = f.read()

    llm = LLM(model="anthropic/claude-sonnet-4-5")

    # ---- Stage 1: Scout -> Fit ----
    scout = build_job_scout(llm)
    fit_analyst = build_fit_analyst(llm)

    scout_task = build_scout_task(scout, job_posting_text)
    fit_task = build_fit_task(fit_analyst, scout_task)

    stage1 = Crew(
        agents=[scout, fit_analyst],
        tasks=[scout_task, fit_task],
        process=Process.sequential,
    )
    stage1_result = stage1.kickoff()

    scout_output = str(scout_task.output)
    fit_output = str(fit_task.output)
    verdict = parse_verdict(fit_output)

    print("\n" + "=" * 60)
    print("STAGE 1 RESULT -- JOB SCOUT + FIT ANALYST")
    print("=" * 60)
    print(fit_output)
    print(f"\nParsed verdict: {verdict}")

    if verdict != "RECOMMEND" and not force:
        print(
            "\nVerdict is SKIP. Not drafting a proposal. Re-run with "
            "--force to draft one anyway."
        )
        return

    # ---- Stage 2: Research -> Proposal ----
    researcher = build_client_researcher(llm)
    writer = build_proposal_writer(llm)

    research_task = build_research_task(researcher, scout_output)

    stage2_research = Crew(
        agents=[researcher],
        tasks=[research_task],
        process=Process.sequential,
    )
    stage2_research.kickoff()
    research_output = str(research_task.output)

    proposal_task = build_proposal_task(
        writer, job_posting_text, fit_output, research_output
    )
    stage2_proposal = Crew(
        agents=[writer],
        tasks=[proposal_task],
        process=Process.sequential,
    )
    stage2_proposal.kickoff()
    proposal_output = str(proposal_task.output)

    print("\n" + "=" * 60)
    print("STAGE 2 RESULT -- CLIENT RESEARCH")
    print("=" * 60)
    print(research_output)

    print("\n" + "=" * 60)
    print("FINAL PROPOSAL")
    print("=" * 60)
    print(proposal_output)


if __name__ == "__main__":
    main()
