import pytest

from scripts.run_lean_svelte_repair import wait_admission


def quota(primary):
    return {'ordinary_allowed': True, 'primary': {'usedPercent': primary},
            'secondary': {'usedPercent': 29}}


def test_waits_for_natural_admission_before_returning():
    values = iter([quota(85), quota(80), quota(1)])
    events = []
    wait_admission(10000, lambda: next(values), lambda: events.append('validate'),
                   lambda q: events.append(q['primary']['usedPercent']),
                   clock=lambda: 0, sleep=lambda n: events.append(('sleep', n)))
    assert events == ['validate', 85, ('sleep', 60), 'validate', 80,
                      ('sleep', 60), 'validate', 1]


def test_deadline_blocks_before_account_or_model_work():
    def unexpected():
        pytest.fail('Account inspection must not run after headroom exhaustion')
    with pytest.raises(RuntimeError, match='headroom'):
        wait_admission(1499, unexpected, lambda: None, lambda q: None,
                       clock=lambda: 0)


def test_unknown_quota_fails_closed_without_waiting():
    with pytest.raises(KeyError):
        wait_admission(10000, lambda: {}, lambda: None, lambda q: None,
                       clock=lambda: 0, sleep=lambda n: pytest.fail('Unknown quota'))
