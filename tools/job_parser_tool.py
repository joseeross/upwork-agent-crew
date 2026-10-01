"""Deterministic (non-LLM) extraction of the structured fields Upwork always
puts in a posting -- rate, hours, duration, experience level -- so the Fit
Analyst gets clean facts instead of re-reading free text for numbers every
time. Pure regex/string logic: no model call, no hallucination risk here.
"""

import re

from crewai.tools import BaseTool


def _extract_rate(text: str) -> str:
    hourly = re.search(r"\$(\d+(?:\.\d+)?)\s*-\s*\$?(\d+(?:\.\d+)?)\s*/?\s*hr", text, re.I)
    if hourly:
        return f"${hourly.group(1)}-${hourly.group(2)}/hr"
    single_hourly = re.search(r"\$(\d+(?:\.\d+)?)\s*/\s*hr", text, re.I)
    if single_hourly:
        return f"${single_hourly.group(1)}/hr"
    fixed = re.search(r"fixed[- ]price", text, re.I)
    if fixed:
        return "Fixed-price (see posting for budget)"
    return "Not stated"


def _extract_hours(text: str) -> str:
    m = re.search(r"(Less than \d+|More than \d+|\d+\s*-\s*\d+)\s*hrs?/week", text, re.I)
    return m.group(0) if m else "Not stated"


def _extract_duration(text: str) -> str:
    m = re.search(r"(\d+\s*to\s*\d+\s*months|\d+\+?\s*months|less than (?:one|1) month)", text, re.I)
    return m.group(0) if m else "Not stated"


def _extract_level(text: str) -> str:
    for level in ("Entry", "Intermediate", "Expert"):
        if re.search(rf"\b{level}\b", text):
            return level
    return "Not stated"


def _extract_video_requirement(text: str) -> bool:
    return bool(re.search(r"\b(1|one)[- ]minute video\b", text, re.I))


def _extract_screening_phrase(text: str) -> str:
    m = re.search(r'phrase ["“]([^"”]+)["”]', text, re.I)
    return m.group(1) if m else ""


class ParseJobPostingTool(BaseTool):
    name: str = "parse_job_posting"
    description: str = (
        "Extracts structured facts (rate, weekly hours, duration, experience "
        "level, whether a video is required, and any required screening "
        "phrase) from a raw pasted Upwork job posting. Pass the full posting "
        "text. Deterministic regex extraction -- not a model call."
    )

    def _run(self, posting_text: str) -> str:
        return (
            f"rate: {_extract_rate(posting_text)}\n"
            f"weekly_hours: {_extract_hours(posting_text)}\n"
            f"duration: {_extract_duration(posting_text)}\n"
            f"experience_level: {_extract_level(posting_text)}\n"
            f"video_required: {_extract_video_requirement(posting_text)}\n"
            f"required_screening_phrase: \"{_extract_screening_phrase(posting_text)}\"\n"
        )
