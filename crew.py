"""Entrypoint: run the Upwork crew against a job posting.

Usage:
    python crew.py path/to/posting.txt
    python crew.py path/to/posting.txt --force   # run proposal stage even on SKIP

The same pipeline is exposed over HTTP by api.py for the n8n workflow
in n8n/ -- see run_pipeline().

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


def load_api_key() -> None:
    """Load .env, then accept CREW_ANTHROPIC_API_KEY as an alias.

    Some hosts (e.g. Claude Code cloud environments) reserve the
    ANTHROPIC_API_KEY name, so the key can be supplied under the alias
    instead. CrewAI itself only reads ANTHROPIC_API_KEY.
    """
    load_dotenv()
    alias = os.environ.get("CREW_ANTHROPIC_API_KEY")
    if alias and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = alias


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


def run_pipeline(job_posting_text: str, force: bool = False) -> dict:
    """Run both stages and return every intermediate output.

    Shared by the CLI below and by api.py (the HTTP wrapper n8n calls).
    Stage 2 only runs on RECOMMEND or when force=True; otherwise
    research_output and proposal come back as empty strings.
    """
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
    stage1.kickoff()

    scout_output = str(scout_task.output)
    fit_output = str(fit_task.output)
    verdict = parse_verdict(fit_output)

    result = {
        "verdict": verdict,
        "forced": force and verdict != "RECOMMEND",
        "scout_output": scout_output,
        "fit_output": fit_output,
        "research_output": "",
        "proposal": "",
    }
    if verdict != "RECOMMEND" and not force:
        return result

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

    result["research_output"] = research_output
    result["proposal"] = str(proposal_task.output)
    return result


def main():
    load_api_key()

    if len(sys.argv) < 2:
        print("Usage: python crew.py path/to/posting.txt [--force]")
        sys.exit(1)

    posting_path = sys.argv[1]
    force = "--force" in sys.argv[2:]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY (or CREW_ANTHROPIC_API_KEY) is not set. "
            "Copy .env.example to .env and "
            "add your key -- this crew makes real model calls and has no "
            "offline fallback."
        )
        sys.exit(1)

    with open(posting_path, "r", encoding="utf-8") as f:
        job_posting_text = f.read()

    result = run_pipeline(job_posting_text, force=force)

    print("\n" + "=" * 60)
    print("STAGE 1 RESULT -- JOB SCOUT + FIT ANALYST")
    print("=" * 60)
    print(result["fit_output"])
    print(f"\nParsed verdict: {result['verdict']}")

    if not result["proposal"]:
        print(
            "\nVerdict is SKIP. Not drafting a proposal. Re-run with "
            "--force to draft one anyway."
        )
        return

    print("\n" + "=" * 60)
    print("STAGE 2 RESULT -- CLIENT RESEARCH")
    print("=" * 60)
    print(result["research_output"])

    print("\n" + "=" * 60)
    print("FINAL PROPOSAL")
    print("=" * 60)
    print(result["proposal"])


if __name__ == "__main__":
    main()
