import json

import pytest

from scripts.run_coding_seventeen import assert_unused, classify, locked_cases, report


def scope():
    cases = [{"id": str(n)} for n in range(17)]
    proposal = {"cases": cases, "image_pins": {c["id"]: {} for c in cases}}
    results = {"rows": [{"case": str(n), "passed": n < 17} for n in range(25)]}
    return cases, proposal, results


def test_exact_seventeen_passing_scope_has_no_substitution():
    cases, p, r = scope()
    assert locked_cases(p, r) == cases
    for bad in [
        {**p, "cases": list(reversed(cases))},
        {**p, "cases": cases[:-1]},
        {**p, "image_pins": {"other": {}}},
    ]:
        with pytest.raises(RuntimeError):
            locked_cases(bad, r)


def test_scored_and_interrupted_prior_coding_cannot_be_replaced(tmp_path):
    cases, _, _ = scope()
    p = tmp_path / "score.json"
    p.write_text(json.dumps({"case": "0"}))
    with pytest.raises(RuntimeError, match="consumed"):
        assert_unused(cases, {str(p): "hash"}, [])
    with pytest.raises(RuntimeError, match="consumed"):
        assert_unused(cases, {}, [tmp_path / "lean-0-1/state/native-state.json"])
    assert_unused(cases, {}, [])


def score(key, **kwargs):
    return {
        "case": key,
        "official_resolved": False,
        "acceptance": {"candidate_commit": "commit"},
        "observed_tokens": 100,
        "seconds": 2,
        **kwargs,
    }


@pytest.mark.parametrize(
    "extra,expected",
    [
        ({"official_resolved": True}, "official_resolution"),
        ({"grader_error": "setup"}, "grader_infrastructure_error"),
        ({"candidate_patch_error": "apply"}, "patch_rejected"),
        ({"acceptance": {"candidate_commit": None}}, "no_accepted_candidate"),
        ({"unobserved_acceptance_tests": 1}, "required_tests_unobserved"),
        ({}, "observed_required_test_failure"),
    ],
)
def test_official_classifications_are_separate(extra, expected):
    assert classify(score("a", **extra)) == expected


def test_shared_report_counts_active_usage_and_all_seventeen(monkeypatch, tmp_path):
    cases, _, _ = scope()
    (tmp_path / "tasks/a").mkdir(parents=True)
    (tmp_path / "tasks/b").mkdir()
    monkeypatch.setattr(
        "scripts.run_coding_seventeen.usage",
        lambda p: (
            ([score("0", official_resolved=True)], 100, [])
            if p.name == "a"
            else ([], 70, ["pending"])
        ),
    )
    result = report(tmp_path, {"cases": [c["id"] for c in cases], "limitations": "selected"})
    assert (
        result["planned_trials"] == 17 and result["scored_trials"] == 1 and not result["complete"]
    )
    assert result["reported_tokens"] == 170 and result["unscored_runs"] == ["pending"]
    assert result["official_resolutions"] == 1
    monkeypatch.setattr("scripts.run_coding_seventeen.usage", lambda p: ([score("0")], 100, []))
    with pytest.raises(RuntimeError, match="duplicate"):
        report(tmp_path, {"cases": ["0"], "limitations": "selected"})


def test_complete_requires_all_seventeen_distinct_official_scores(monkeypatch, tmp_path):
    cases, _, _ = scope()
    for case in cases:
        (tmp_path / "tasks" / case["id"]).mkdir(parents=True)
    monkeypatch.setattr("scripts.run_coding_seventeen.usage", lambda p: ([score(p.name)], 100, []))
    result = report(tmp_path, {"cases": [c["id"] for c in cases], "limitations": "selected"})
    assert result["complete"] and result["scored_trials"] == 17
    assert result["reported_tokens"] == 1700 and result["official_resolutions"] == 0
