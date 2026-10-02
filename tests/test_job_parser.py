"""Tests for the deterministic job-posting parser. No model calls."""

from pathlib import Path

import pytest

from tools.job_parser_tool import (
    ParseJobPostingTool,
    _extract_duration,
    _extract_hours,
    _extract_level,
    _extract_rate,
    _extract_screening_phrase,
    _extract_video_requirement,
)

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample_posting.txt"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("$45.00-$70.00/hr", "$45.00-$70.00/hr"),
        ("$45.00 - $70.00 Hourly", "$45.00-$70.00/hr"),
        ("Hourly: $45.00-$70.00", "$45.00-$70.00/hr"),
        ("$60/hr", "$60/hr"),
        ("$55.00 Hourly", "$55.00/hr"),
        ("Hourly: $50", "$50/hr"),
        ("Fixed-price\nBudget: $1,500", "Fixed-price $1500"),
        ("$500 Fixed-price", "Fixed-price $500"),
        ("Fixed price project, budget TBD", "Fixed-price (see posting for budget)"),
        ("No numbers here", "Not stated"),
    ],
)
def test_extract_rate(text, expected):
    assert _extract_rate(text) == expected


def test_hours_duration_level():
    text = "Less than 30 hrs/week\n1 to 3 months\nExpert"
    assert _extract_hours(text) == "Less than 30 hrs/week"
    assert _extract_duration(text) == "1 to 3 months"
    assert _extract_level(text) == "Expert"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Include a 1-minute video intro", True),
        ("Please send a short Loom walking through it", True),
        ("Record a video of a similar build", True),
        ("Just a text proposal please", False),
    ],
)
def test_video_requirement(text, expected):
    assert _extract_video_requirement(text) is expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ('Include the phrase "blue banana" in your proposal', "blue banana"),
        ('Start your proposal with the word "TICKETBOT".', "TICKETBOT"),
        ("Start your proposal with “READY”", "READY"),
        ("No special instructions", ""),
    ],
)
def test_screening_phrase(text, expected):
    assert _extract_screening_phrase(text) == expected


def test_sample_posting_end_to_end():
    out = ParseJobPostingTool()._run(SAMPLE.read_text())
    assert "rate: $45.00-$70.00/hr" in out
    assert "weekly_hours: Less than 30 hrs/week" in out
    assert "duration: 1 to 3 months" in out
    assert "experience_level: Expert" in out
    assert "video_required: True" in out
    assert 'required_screening_phrase: "TICKETBOT"' in out
