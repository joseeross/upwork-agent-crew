"""Task definitions for the crew's two-stage pipeline.

Stage 1 (one Crew run): Job Scout -> Fit Analyst.
  Uses CrewAI's native `context=[...]` so the Fit Analyst automatically
  sees the Scout's output within the same crew run.

Stage 2 (a second Crew run, only kicked off if stage 1 recommends the job,
or the user overrides): Client Researcher + Proposal Writer.
  This runs as a separate Crew instance, so stage-1 results are passed in
  as plain text rather than CrewAI Task objects (context tracking only
  works for tasks inside the same crew run).

See crew.py for the gating logic between the two stages.
"""

from crewai import Task


def build_scout_task(agent, job_posting_text: str) -> Task:
    return Task(
        description=(
            "Here is a raw Upwork job posting:\n\n"
            f"---\n{job_posting_text}\n---\n\n"
            "Extract: the core job description in 2-3 sentences, required "
            "skills, rate, weekly hours, contract duration, experience "
            "level, any client/company name mentioned, and ALL hard "
            "application requirements (e.g. a required video, a required "
            "exact phrase, required screening questions to answer). List "
            "screening questions verbatim if present."
        ),
        expected_output=(
            "A structured summary with these exact sections: Description, "
            "Required Skills, Rate, Hours, Duration, Experience Level, "
            "Client/Company Name (or 'not given'), Hard Requirements, "
            "Screening Questions."
        ),
        agent=agent,
    )


def build_fit_task(agent, scout_task: Task) -> Task:
    return Task(
        description=(
            "Using the job summary above and Jose's freelancer profile "
            "(call load_freelancer_profile), score this job's fit. Cover: "
            "stack match, rate match, client-quality signals if visible, "
            "and any realistic gap (e.g. the posting wants deployed-client "
            "results and Jose's portfolio is strong self-directed work, "
            "not live client case studies -- name that kind of gap "
            "explicitly if it applies, don't paper over it). "
            "End the response with a line in exactly this format so it can "
            "be parsed automatically: VERDICT: RECOMMEND or VERDICT: SKIP, "
            "followed by a one-line reason on the same line."
        ),
        expected_output=(
            "Sections: Stack Match, Rate Match, Client Quality Signals, "
            "Gaps/Risks, then a final line starting with 'VERDICT: '."
        ),
        agent=agent,
        context=[scout_task],
    )


def build_research_task(agent, scout_summary_text: str) -> Task:
    return Task(
        description=(
            "Here is a job summary produced earlier:\n\n"
            f"---\n{scout_summary_text}\n---\n\n"
            "If a client or company name is given in it, call "
            "research_client to look them up. If no name is given, or the "
            "tool reports no live search is configured, say exactly that -- "
            "do not invent a client background."
        ),
        expected_output=(
            "Either: real findings about the named client/company with "
            "sources, OR a plain statement that no client name was given "
            "or no live search is available. Never a fabricated profile."
        ),
        agent=agent,
    )


def build_proposal_task(agent, job_posting_text: str, fit_summary_text: str, research_summary_text: str) -> Task:
    return Task(
        description=(
            "Original job posting:\n---\n" + job_posting_text + "\n---\n\n"
            "Fit analysis:\n---\n" + fit_summary_text + "\n---\n\n"
            "Client research:\n---\n" + research_summary_text + "\n---\n\n"
            "Write a tailored Upwork proposal for this job in Jose's voice: "
            "direct, specific, senior-engineer tone, no generic filler.\n"
            "Requirements:\n"
            "1. Open with the single most relevant thing Jose has actually "
            "built (his Claude-based RAG/agent repos), not a generic intro.\n"
            "2. If the posting has screening questions, answer each one "
            "directly in the proposal body.\n"
            "3. If the posting requires an exact phrase, include it "
            "verbatim, unchanged.\n"
            "4. If the fit analysis flagged a real gap (e.g. no live client "
            "deployment results), address it honestly in one sentence "
            "rather than implying something that isn't true.\n"
            "5. Never state a specific dollar figure, hours-saved number, "
            "or client outcome that wasn't actually given to you as fact."
        ),
        expected_output=(
            "The final proposal text, ready to paste into Upwork, plus a "
            "short separate note flagging anything the posting requires "
            "that this proposal cannot fulfill on its own (e.g. 'still "
            "need to record and attach the 1-minute video')."
        ),
        agent=agent,
    )
