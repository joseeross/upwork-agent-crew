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
