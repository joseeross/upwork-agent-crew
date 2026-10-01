"""Client/company research tool.

Honesty note: Upwork does not expose a public API for client history to
third-party tools, and this project ships with no paid search API wired in
by default. Rather than let the agent invent a plausible-sounding client
background (a real risk with LLM tool-calling), this tool is explicit about
what it can and can't do:

  - If SERPER_API_KEY is set in the environment, it runs a real web search
    via Serper.dev and returns actual results.
  - If it is not set, it returns a clear "no live search configured" message
    instead of fabricating anything, so the agent reports that limitation
    to the user rather than presenting a guess as fact.
"""

import os

import requests
from crewai.tools import BaseTool


class ClientResearchTool(BaseTool):
    name: str = "research_client"
    description: str = (
        "Searches the web for public information about a client/company "
        "name mentioned in a job posting (news, website, reviews). Returns "
        "real search results if SERPER_API_KEY is configured, otherwise "
        "returns a note that no live search is available -- never invents "
        "company background."
    )

    def _run(self, query: str) -> str:
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            return (
                "NO LIVE SEARCH CONFIGURED: set SERPER_API_KEY in .env to "
                "enable real client research. Do not fabricate findings -- "
                "tell the user this step was skipped."
            )
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            return f"SEARCH FAILED ({exc}). Do not fabricate findings."

        results = data.get("organic", [])[:5]
        if not results:
            return "No results found for this query."
        lines = []
        for r in results:
            lines.append(f"- {r.get('title')}: {r.get('snippet', '')} ({r.get('link')})")
        return "\n".join(lines)
