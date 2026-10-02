"""Deterministic (non-LLM) extraction of the structured fields Upwork always
puts in a posting -- rate, hours, duration, experience level -- so the Fit
Analyst gets clean facts instead of re-reading free text for numbers every
time. Pure regex/string logic: no model call, no hallucination risk here.
"""

import re

from crewai.tools import BaseTool


_MONEY = r"\$\s?(\d[\d,]*(?:\.\d+)?)"


def _money(raw: str) -> str:
    return raw.replace(",", "")


def _extract_rate(text: str) -> str:
    # Hourly range: "$45.00-$70.00/hr", "$45 - $70 Hourly", "Hourly: $45-$70"
    rng = re.search(_MONEY + r"\s*(?:-|to|–)\s*" + _MONEY, text, re.I)
    hourly_hint = re.search(r"/\s*hr\b|\bhourly\b|\bper hour\b", text, re.I)
    if rng and hourly_hint:
        return f"${_money(rng.group(1))}-${_money(rng.group(2))}/hr"
    single_hourly = re.search(_MONEY + r"\s*(?:/\s*hr\b|per hour\b|hourly\b)", text, re.I) or re.search(
        r"\bhourly\s*:?\s*" + _MONEY, text, re.I
    )
    if single_hourly:
        return f"${_money(single_hourly.group(1))}/hr"
    if re.search(r"fixed[- ]price", text, re.I):
        budget = re.search(r"(?:budget|fixed[- ]price)\s*:?\s*" + _MONEY, text, re.I) or re.search(
            _MONEY + r"\s*fixed[- ]price", text, re.I
        )
        if budget:
            return f"Fixed-price ${_money(budget.group(1))}"
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
    # "1-minute video", "Loom video", "record a video", "include a Loom"
    return bool(re.search(r"\bloom\b|\bvideo\b", text, re.I))


def _extract_screening_phrase(text: str) -> str:
    # 'phrase "X"', 'the word "X"', 'start your proposal with "X"'
    m = re.search(r'(?:phrase|word|words|with)\s*:?\s*["“]([^"”]+)["”]', text, re.I)
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
