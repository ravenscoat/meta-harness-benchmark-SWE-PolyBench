"""Repair attempts must preserve provenance and exclude prior successes."""
from types import SimpleNamespace

import pytest

from benchmarks.polybench.lean import LeanEngine
from hx.models import Candidate
from scripts import run_solution_repairs as module


def saved(commit='candidate'):
    return Candidate(base_commit='original', input_commit='original', candidate_commit=commit,
                     workspace='/saved', diff_sha256='hash', changed_files=['app.js'])


def fake_init(self, *args, **kwargs):
    self.case = {'id': 'one'}
    self.config = {'fingerprint': 'old', 'settings': 'fixture'}


def engine(monkeypatch, commit='candidate', context=None):
    monkeypatch.setattr(LeanEngine, '__init__', fake_init)
    return module.SeededRepair(seeds={'one': saved(commit).model_dump()},
                              contexts={'one': context or {'public': 'issue'}}, admission=lambda: None)


def test_seed_and_public_context_change_identity(monkeypatch):
    first = engine(monkeypatch).config['fingerprint']
    assert first != engine(monkeypatch, commit='other').config['fingerprint']
    assert first != engine(monkeypatch, context={'public': 'different'}).config['fingerprint']
    assert first == engine(monkeypatch).config['fingerprint']


def test_first_call_uses_saved_candidate_but_revision_keeps_new_candidate(monkeypatch):
    subject = engine(monkeypatch)
    calls = []
    monkeypatch.setattr(module, 'validate_candidate', lambda candidate, task: calls.append(candidate))
    monkeypatch.setattr(LeanEngine, '_implementation',
                        lambda self, run, step, task, previous, feedback, deadline: (task, previous, feedback))
    task = SimpleNamespace(base_commit='original')
    result = subject._implementation('run', 'implement', task, None, {}, 100)
    assert result[0] is task
    assert result[1].candidate_commit == 'candidate'
    assert result[2] == {'public': 'issue'}
    replacement = saved('new')
    assert subject._implementation('run', 'revise_1', task, replacement, {'repair': True}, 100)[1] is replacement
    assert len(calls) == 1
    with pytest.raises(RuntimeError, match='different original base'):
        subject._implementation('run', 'implement', SimpleNamespace(base_commit='foreign'), None, {}, 100)


def test_exact_nine_failures_exclude_success():
    failed = ['mui__material-ui-13534', *['task' + str(i) for i in range(8)]]
    audit = {'records': [{'score': {'case': key, 'official_resolved': False}} for key in failed]
             + [{'score': {'case': 'successful', 'official_resolved': True}}]}
    assert module.repair_cases(audit) == failed
    audit['records'].append(audit['records'][0])
    with pytest.raises(RuntimeError, match='nine'):
        module.repair_cases(audit)


def test_active_usage_counts_without_forbidding_its_own_worker():
    plan = {'max_reported_tokens': 1000000, 'deadline': 5000}
    result = {'reported_tokens': 200000, 'unscored_runs': ['current-run']}
    module.budget_guard(plan, result, 100, False)
    with pytest.raises(RuntimeError, match='Unscored'):
        module.budget_guard(plan, result, 100, True)
    with pytest.raises(RuntimeError, match='headroom'):
        module.budget_guard(plan, {**result, 'reported_tokens': 900000}, 100, False)
    with pytest.raises(RuntimeError, match='headroom'):
        module.budget_guard(plan, {**result, 'unscored_runs': []}, 4900, True)


def test_report_counts_all_children_and_rejects_duplicate_scores(monkeypatch, tmp_path):
    for name in ['one', 'two']:
        (tmp_path / 'tasks' / name).mkdir(parents=True)
    def usage(child):
        if child.name == 'two':
            return [], 55, ['active']
        return [{'case': 'one', 'official_resolved': False, 'acceptance': {'candidate_commit': 'c'},
                 'seconds': 2}], 100, []
    monkeypatch.setattr(module, 'usage', usage)
    result = module.report(tmp_path, {'cases': ['one', 'two']})
    assert result['reported_tokens'] == 155
    assert result['unscored_runs'] == ['active']
    assert result['scored_trials'] == 1 and result['complete'] is False
    monkeypatch.setattr(module, 'usage', lambda child: usage(tmp_path / 'tasks/one'))
    with pytest.raises(RuntimeError, match='duplicate'):
        module.report(tmp_path, {'cases': ['one', 'two']})
