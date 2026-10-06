import pytest

from scripts.run_lean_three import REPOS, check_headroom, select_cases


def test_selection_excludes_consumed_tasks_and_is_order_independent():
    rows = [{'repo': repo, 'instance_id': repo + str(n), 'language': 'JavaScript',
             'task_category': 'Bug Fix', 'problem_statement': 'Public issue behavior',
             'base_commit': 'a' * 40} for repo in REPOS for n in range(3)]
    excluded = {repo + '0' for repo in REPOS}
    chosen = select_cases(rows, excluded)
    assert chosen == select_cases(list(reversed(rows)), excluded)
    assert [c['repo'] for c in chosen] == REPOS
    assert not {c['id'] for c in chosen} & excluded
    with pytest.raises(RuntimeError, match='No untouched'):
        select_cases(rows, {r['instance_id'] for r in rows})


def test_batch_guards_count_active_usage_and_reserve_next_task():
    plan = {'max_reported_tokens': 1500000, 'deadline': 14400}
    check_headroom(1050000, 12899, plan, True)
    with pytest.raises(RuntimeError, match='headroom'):
        check_headroom(1050001, 0, plan, True)
    with pytest.raises(RuntimeError, match='headroom'):
        check_headroom(0, 12900, plan, True)
    check_headroom(1300000, 13000, plan, False)
    with pytest.raises(RuntimeError, match='headroom'):
        check_headroom(1350001, 0, plan, False)
