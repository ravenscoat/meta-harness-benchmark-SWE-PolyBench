import json

import pytest

from scripts.run_paper_benchmark import CASES, guard_budget, validate_fresh


def test_only_two_original_benchmark_cases():
    assert CASES == ["langchain-ai__langchain-4579", "mui__material-ui-18683"]


def test_already_scored_evaluation_is_not_fresh(tmp_path):
    score = tmp_path / "score.json"
    score.write_text(json.dumps({"case": CASES[0]}))
    with pytest.raises(RuntimeError, match="already"):
        validate_fresh(CASES, {str(score): "hash"})


def test_batch_stops_before_an_unaffordable_call():
    plan = {"deadline": 10000, "max_reported_tokens": 1200000}
    guard_budget(plan, 600000, now=1000)
    with pytest.raises(RuntimeError, match="token"):
        guard_budget(plan, 700000, now=1000)
    with pytest.raises(RuntimeError, match="window"):
        guard_budget(plan, 0, now=9000)
