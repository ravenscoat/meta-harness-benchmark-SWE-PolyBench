from benchmarks.polybench.metrics import aggregate, classification


def row(**updates):
    return {"status": "ready_for_approval", "acceptance": {"candidate_commit": "a"},
        "observed_tokens": 10, "seconds": 2, **updates}


def test_efficiency_includes_failed_attempt_costs():
    result = aggregate([row(official_resolved=True, task_success=True),
                        row(candidate_patch_error="rejected")], wall_seconds=20)
    assert result["reported_tokens_per_official_resolution"] == 20
    assert result["readiness_precision"] == .5
    assert result["outcomes"] == {"official_resolution": 1, "patch_rejected": 1}


def test_zero_success_does_not_appear_free():
    result = aggregate([row(candidate_patch_error="rejected")])
    assert result["reported_tokens"] == 10
    assert result["reported_tokens_per_official_resolution"] is None
    assert result["readiness_precision"] == 0
    assert aggregate([])["readiness_precision"] is None


def test_no_candidate_zero_missing_count_is_not_observed_behavioral_failure():
    assert classification(row(acceptance={"candidate_commit": None},
                              unobserved_acceptance_tests=0)) == "no_accepted_candidate"
    assert classification(row(unobserved_acceptance_tests=2)) == "required_tests_unobserved"
