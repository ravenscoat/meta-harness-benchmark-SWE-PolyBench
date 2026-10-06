import json
import time

import pytest

from scripts import run_parallel_three as batch


def test_shared_pending_calls_reserve_batch_budget(tmp_path, monkeypatch):
    (tmp_path / 'plan.json').write_text(json.dumps({
        'deadline': time.time() + 3600, 'max_reported_tokens': 1000000,
    }))
    (tmp_path / 'reservations.json').write_text(json.dumps({'other-task': 350000}))
    monkeypatch.setattr(batch, 'totals', lambda _: ([], 400000, []))
    monkeypatch.setattr(batch, 'account_usage', lambda *_: {
        'ordinary_allowed': True, 'primary': {'usedPercent': 10},
        'secondary': {'usedPercent': 92},
    })
    with pytest.raises(RuntimeError, match='headroom'):
        batch.guard(tmp_path, batch.CASES[0], 'implement')
    assert json.loads((tmp_path / 'reservations.json').read_text()) == {'other-task': 350000}
    batch.guard(tmp_path, batch.CASES[0], 'independent_challenge')
    assert json.loads((tmp_path / 'reservations.json').read_text()) == {
        'other-task': 350000, batch.CASES[0]: 150000,
    }


def test_quota_stops_new_parallel_calls():
    quota = {'ordinary_allowed': True, 'primary': {'usedPercent': 10},
             'secondary': {'usedPercent': 98}}
    assert not batch.quota_allowed(quota)
    quota['secondary']['usedPercent'] = 92
    assert batch.quota_allowed(quota)
    quota['ordinary_allowed'] = False
    assert not batch.quota_allowed(quota)


def test_totals_include_unscored_usage_from_all_three(tmp_path, monkeypatch):
    for key in batch.CASES:
        (tmp_path / 'tasks' / key).mkdir(parents=True)
    observations = iter([
        ([{'official_resolved': True}], 100, []),
        ([], 200, ['run-in-progress']),
        ([{'official_resolved': False}], 300, []),
    ])
    monkeypatch.setattr(batch, 'usage', lambda _: next(observations))
    rows, tokens, incomplete = batch.totals(tmp_path)
    assert len(rows) == 2
    assert tokens == 600
    assert incomplete == ['run-in-progress']
