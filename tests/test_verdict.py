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
