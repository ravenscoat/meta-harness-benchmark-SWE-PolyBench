import pytest

from scripts.run_five_failure_development import SOURCES, eligible_failure, guard_budget


def test_selection_contains_exactly_five_distinct_known_failed_tasks():
    assert len(SOURCES) == len({key for key, _ in SOURCES}) == 5
    assert "sveltejs__svelte-728" not in {key for key, _ in SOURCES}


def test_no_candidate_patch_and_infrastructure_failures_are_not_behavioral_failures():
    row = {"official_resolved": False, "acceptance": {"candidate_commit": "candidate"},
        "unobserved_acceptance_tests": 0}
    assert eligible_failure(row)
    for changed in ({"official_resolved": True}, {"acceptance": {}},
        {"candidate_patch_error": "patch rejected"}, {"grader_error": "setup"},
        {"unobserved_acceptance_tests": 1}, {"unobserved_acceptance_tests": None}):
        assert not eligible_failure({**row, **changed})


def test_guards_reserve_workflow_headroom_and_allow_bounded_repair_window():
    plan = {"deadline": 3000, "max_reported_tokens": 3500000}
    guard_budget(plan, 2000000, 1000)
    guard_budget(plan, 3000000, 2000, worker=True)
    with pytest.raises(RuntimeError, match="token"):
        guard_budget(plan, 3000000, 1000)
    with pytest.raises(RuntimeError, match="deadline"):
        guard_budget(plan, 0, 2000)
    with pytest.raises(RuntimeError, match="deadline"):
        guard_budget(plan, 0, 2500, worker=True)
