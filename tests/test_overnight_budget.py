import pytest

from scripts.run_hx_overnight import budget_guard


def test_trial_needs_time_and_reported_token_headroom():
    plan = {"deadline": 10000, "max_additional_reported_tokens": 6000000}
    budget_guard(plan, {"additional_reported_tokens": 607462}, now=1000)
    with pytest.raises(RuntimeError, match="deadline"):
        budget_guard(plan, {"additional_reported_tokens": 0}, now=9100)
    with pytest.raises(RuntimeError, match="token"):
        budget_guard(plan, {"additional_reported_tokens": 5250001}, now=1000)
