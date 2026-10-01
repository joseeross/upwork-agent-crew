"""Loads Jose's freelance profile so agents never have to guess at facts
like rate range or stack -- they read it from config/profile.yaml."""

from pathlib import Path

import yaml
from crewai.tools import BaseTool

PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "profile.yaml"


class LoadFreelancerProfileTool(BaseTool):
    name: str = "load_freelancer_profile"
    description: str = (
        "Returns Jose Ross's freelance profile as YAML text: stack, target "
        "roles, rate range, availability, client preferences, and red flags. "
        "Always call this before scoring a job's fit -- never assume profile "
        "details from memory."
    )

    def _run(self) -> str:
        if not PROFILE_PATH.exists():
            return "ERROR: profile.yaml not found at " + str(PROFILE_PATH)
        return PROFILE_PATH.read_text(encoding="utf-8")
