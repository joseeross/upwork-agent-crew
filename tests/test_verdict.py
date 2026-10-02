from crew import parse_verdict


def test_recommend():
    assert parse_verdict("analysis...\nVERDICT: RECOMMEND") == "RECOMMEND"


def test_skip_and_missing_default_to_skip():
    assert parse_verdict("VERDICT: SKIP") == "SKIP"
    assert parse_verdict("no verdict line at all") == "SKIP"
