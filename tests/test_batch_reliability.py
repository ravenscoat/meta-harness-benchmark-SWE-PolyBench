import json
import time
from pathlib import Path

import pytest

from scripts import run_batch_reliability as batch


def setup_batch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path('.hx').mkdir()
    root = tmp_path/'batch'
    root.mkdir()
    plan = {'cases': batch.CASES, 'started': time.time(), 'not_before': 0,
            'deadline': time.time()+14400, 'max_reported_tokens': 3600000,
            'historical_scores': {}, 'prior_coding_exposure': dict.fromkeys(batch.CASES, False),
            'limitations': 'fixture'}
    (root/'plan.json').write_text(json.dumps(plan))
    for key in batch.CASES:
        (root/'tasks'/key/'experiments/heldout-results').mkdir(parents=True)
    monkeypatch.setattr(batch, 'validate', lambda *_: None)
    monkeypatch.setattr(batch, 'account_usage', lambda *_: {
        'ordinary_allowed': True, 'primary': {'usedPercent': 1},
        'secondary': {'usedPercent': 16}})
    return root, plan


def test_one_completed_question_never_counts_as_completed_batch(tmp_path, monkeypatch):
    root, plan = setup_batch(tmp_path, monkeypatch)
    folder = root/'tasks'/batch.CASES[0]/'experiments/heldout-results/fixture'
    folder.mkdir()
    (folder/'score.json').write_text(json.dumps({'case': batch.CASES[0],
        'official_resolved': True, 'task_success': True, 'observed_tokens': 50}))
    result = batch.report(root, plan)
    assert result['scored_trials'] == 1 and not result['complete']
    assert len(result['remaining_cases']) == 2


def test_preparation_failure_prevents_every_model_task(tmp_path, monkeypatch):
    root, _ = setup_batch(tmp_path, monkeypatch)
    checked, called = [], []
    def probe(_, key):
        checked.append(key)
        if key == batch.CASES[1]:
            raise RuntimeError('unsupported build recipe')
        return {'container_id': key}
    monkeypatch.setattr(batch, 'preflight', probe)
    monkeypatch.setattr(batch.runner, 'run_case', lambda *args, **kwargs: called.append(args))
    with pytest.raises(RuntimeError, match='unsupported build'):
        batch.run(root)
    assert checked == batch.CASES[:2] and called == []
    assert json.loads((root/'results.json').read_text())['scored_trials'] == 0


def test_all_three_run_and_failures_are_retained_without_aborting_batch(tmp_path, monkeypatch):
    root, _ = setup_batch(tmp_path, monkeypatch)
    events = []
    def probe(_, key):
        events.append(('preflight', key))
        return {'container_id': key}
    def coding(child, key, *args, **kwargs):
        events.append(('coding', key))
        folder = child/'experiments/heldout-results/fixture'
        folder.mkdir()
        (folder/'score.json').write_text(json.dumps({'case': key,
            'official_resolved': key != batch.CASES[1], 'task_success': key != batch.CASES[1],
            'observed_tokens': 100, 'usage_known': True, 'grader_error': None}))
    monkeypatch.setattr(batch, 'preflight', probe)
    monkeypatch.setattr(batch.runner, 'run_case', coding)
    batch.run(root)
    assert events == [('preflight', k) for k in batch.CASES]+[('coding', k) for k in batch.CASES]
    result = json.loads((root/'results.json').read_text())
    assert result['complete'] and result['scored_trials'] == 3
    assert result['official_resolutions'] == 2 and result['reported_tokens'] == 300


def test_isolation_failure_blocks_coding(tmp_path, monkeypatch):
    root, _ = setup_batch(tmp_path, monkeypatch)
    monkeypatch.setattr(batch, 'preflight', lambda *_: {'container_id': 'same-container'})
    with pytest.raises(RuntimeError, match='isolation'):
        batch.run(root)
