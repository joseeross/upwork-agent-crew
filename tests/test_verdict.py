from crew import parse_verdict


def test_recommend():
    assert parse_verdict("analysis...\nVERDICT: RECOMMEND") == "RECOMMEND"


def test_skip_and_missing_default_to_skip():
    assert parse_verdict("VERDICT: SKIP") == "SKIP"
    assert parse_verdict("no verdict line at all") == "SKIP"


def test_alias_key_is_copied(monkeypatch):
    from crew import load_api_key

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CREW_ANTHROPIC_API_KEY", "alias-value")
    load_api_key()
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "alias-value"


def test_markdown_wrapped_verdict_with_commentary():
    # Real Fit Analyst output from the first live run.
    text = (
        "analysis...\n\n---\n\n"
        "**VERDICT: RECOMMEND** - Stack is a bullseye, rate is perfect. "
        "If client has no history or unverified payment, downgrade to SKIP."
    )
    assert parse_verdict(text) == "RECOMMEND"


def test_markdown_wrapped_skip():
    assert parse_verdict("## VERDICT: **SKIP** - rate too low") == "SKIP"


def test_check_proposal_flags_phrase_and_unknown_links():
    from crew import check_proposal

    posting = 'Start your proposal with the word "TICKETBOT".'
    profile = 'link: "https://github.com/joseeross/upwork-agent-crew"'
    good = "TICKETBOT - I built https://github.com/joseeross/upwork-agent-crew ..."
    assert check_proposal(good, posting, profile) == []

    bad = "Hi! See github.com/joseeross/claude-rag-agent. TICKETBOT"
    warnings = check_proposal(bad, posting, profile)
    assert any("start with" in w for w in warnings)
    assert any("claude-rag-agent" in w for w in warnings)
    assert any("missing" in w for w in check_proposal("Hello", posting, profile))


def test_strip_title_lines():
    from crew import strip_title_lines

    assert strip_title_lines("# Proposal\n\nTICKETBOT\n\nI built...") == "TICKETBOT\n\nI built..."
    assert strip_title_lines("**Upwork Proposal:**\nHi") == "Hi"
    assert strip_title_lines("TICKETBOT\n# Proposal") == "TICKETBOT\n# Proposal"


def test_to_plain_text():
    from crew import to_plain_text

    md = ("I built **[upwork-agent-crew](https://github.com/joseeross/upwork-agent-crew)** "
          "and __more__.\n## Plan\n* step one\n[site](https://example.com)")
    assert to_plain_text(md) == (
        "I built upwork-agent-crew (https://github.com/joseeross/upwork-agent-crew) and more.\n"
        "Plan\n- step one\nsite (https://example.com)"
    )
