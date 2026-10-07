import pytest

from scripts.run_environment_thirty import REPOS, runner_report_passed, select


@pytest.mark.parametrize('title', ['HX environment runner smoke', ' HX environment runner smoke', '\tHX environment runner smoke\n'])
def test_legacy_mocha_outer_whitespace_keeps_exact_smoke_identity(title):
    report = {'stats': {'tests': 1, 'passes': 1, 'failures': 0},
              'passes': [{'fullTitle': title, 'err': {}}], 'failures': []}
    assert runner_report_passed(report)


@pytest.mark.parametrize('field,value', [('tests', 0), ('tests', 2), ('passes', 0), ('failures', 1), ('pending', 1)])
def test_runner_receipt_rejects_missing_extra_failed_or_pending_tests(field, value):
    report = {'stats': {'tests': 1, 'passes': 1, 'failures': 0},
              'passes': [{'fullTitle': ' HX environment runner smoke', 'err': {}}]}
    report['stats'][field] = value
    assert not runner_report_passed(report)


def test_runner_receipt_rejects_wrong_name_and_hidden_error():
    report = {'stats': {'tests': 1, 'passes': 1, 'failures': 0},
              'passes': [{'fullTitle': 'other HX environment runner smoke', 'err': {}}]}
    assert not runner_report_passed(report)
    report['passes'][0] = {'fullTitle': 'HX environment runner smoke', 'err': {'message': 'failed'}}
    assert not runner_report_passed(report)


def fixtures():
    anchors = [{"id": repo + "anchor", "repo": repo} for repo in REPOS]
    rows = [
        {
            "repo": repo,
            "instance_id": repo + str(n),
            "language": "JavaScript",
            "task_category": "Bug Fix",
            "problem_statement": "Requested public behavior",
            "base_commit": "a" * 40,
        }
        for repo in REPOS
        for n in range(12)
    ]
    return anchors, rows


def test_thirty_selection_is_locked_metadata_rank_with_three_anchors():
    anchors, rows = fixtures()
    excluded = {repo + "0" for repo in REPOS}
    selected = select(rows, excluded, anchors)
    assert selected == select(list(reversed(rows)), excluded, anchors)
    assert len(selected) == len({c["id"] for c in selected}) == 30
    assert selected[:3] == anchors
    assert all(sum(c["repo"] == repo for c in selected) == 10 for repo in REPOS)
    assert not excluded & {c["id"] for c in selected}


def test_missing_scope_capacity_is_not_replaced_by_another_repository():
    anchors, rows = fixtures()
    with pytest.raises(ValueError, match="Insufficient"):
        select([r for r in rows if r["repo"] != REPOS[0]], set(), anchors)


def test_missing_or_duplicate_anchor_fails_closed():
    anchors, rows = fixtures()
    with pytest.raises(ValueError, match="anchor"):
        select(rows, set(), anchors[:2])
    with pytest.raises(ValueError, match="anchor"):
        select(rows, set(), anchors + [anchors[0]])

def test_amended_recheck_retains_all_failures_and_original_order():
    from scripts.run_environment_thirty import amended_scope
    cases = [{'id': str(i)} for i in range(30)]
    results = {'complete': True, 'rows': [{'case': str(i), 'passed': i >= 14} for i in range(30)]}
    amendment = {'cases': [str(i) for i in range(25)], 'parent_plan_sha256': 'p', 'parent_results_sha256': 'r', 'window_seconds': 28800, 'model_calls_allowed': 0}
    assert amended_scope(cases, results, amendment, 'p', 'r') == cases[:25]
    for mutation, message in [({'parent_plan_sha256': 'changed'}, 'evidence'), ({'cases': [str(i) for i in range(1,26)]}, 'failed'), ({'cases': ['outside'] + amendment['cases'][1:]}, 'unique'), ({'cases': list(reversed(amendment['cases']))}, 'order'), ({'window_seconds': 30000}, 'eight-hour'), ({'model_calls_allowed': 1}, 'model-free')]:
        with pytest.raises(ValueError, match=message):
            amended_scope(cases, results, {**amendment, **mutation}, 'p', 'r')
    with pytest.raises(ValueError, match='incomplete'):
        amended_scope(cases, {**results, 'complete': False}, amendment, 'p', 'r')
