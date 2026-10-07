"""Transport-only retries and stopped-boundary recovery; no live calls."""
import json
from types import SimpleNamespace

import pytest

from benchmarks.polybench.image_transport import ensure_pinned
from hx.code_search import seal
from hx.models import HXError
from scripts import run_diagnosis_search_recovery as recovery

PIN = {'id': 'case', 'image_id': 'sha256:fixed', 'image_digests': ['repo@sha256:fixed']}


def test_retry_keeps_exact_pin_and_preserves_failed_receipt(tmp_path):
    calls, sleeps = [], []
    def operation(client, root, case):
        calls.append(case)
        if len(calls) == 1:
            raise HXError('read: connection reset by peer')
        return 'image'
    assert ensure_pinned(None, tmp_path, PIN, lambda: None,
                         operation=operation, sleep=sleeps.append) == 'image'
    assert calls == [PIN, PIN] and sleeps == [10]
    receipts = sorted(tmp_path.rglob('attempt-*.json'))
    assert [json.loads(p.read_text())['passed'] for p in receipts] == [False, True]


@pytest.mark.parametrize('message,count', [('unexpected EOF', 3), ('Image identity mismatch', 1)])
def test_retry_bound_and_nontransport_failure(tmp_path, message, count):
    calls = []
    def operation(*args):
        calls.append(1)
        raise HXError(message)
    with pytest.raises(HXError, match=message):
        ensure_pinned(None, tmp_path, PIN, lambda: None, operation=operation, sleep=lambda _: None)
    assert len(calls) == count
    assert len(list(tmp_path.rglob('attempt-*.json'))) == count


def test_deadline_prevents_second_transfer(tmp_path):
    checks = []
    def control():
        checks.append(1)
        if len(checks) == 2:
            raise HXError('deadline exhausted')
    def operation(*args):
        raise HXError('unexpected EOF')
    with pytest.raises(HXError, match='deadline'):
        ensure_pinned(None, tmp_path, PIN, control, operation=operation,
                      sleep=lambda _: pytest.fail('No waiting after expiry'))
    assert len(list(tmp_path.rglob('attempt-*.json'))) == 1


def test_retention_checks_fresh_worker_once_and_releases_only_other_pins(monkeypatch, tmp_path):
    backend = object.__new__(recovery.RecoveryBackend)
    backend.root, backend.prepared, backend.fresh_worker_images = tmp_path, tmp_path, set()
    backend.outer_control = lambda: None
    images = {'case': dict(PIN, repo_path='public'), 'other': {'image_id': 'other'}}
    monkeypatch.setattr(recovery.runner, 'resources',
                        lambda _: (None, images, SimpleNamespace(close=lambda: None), None))
    released, checked = [], []
    monkeypatch.setattr(recovery, 'release_images', lambda c, pins: released.append(pins) or [])
    monkeypatch.setattr(recovery, 'ensure_pinned', lambda *args: None)
    monkeypatch.setattr(recovery, 'worker_environment_check',
                        lambda *args: checked.append(args[1]) or {'passed': True})
    backend.retain('case')
    backend.release('case', tmp_path)
    backend.retain('case')
    assert released == [[images['other']], [images['other']]]
    assert checked == [images['case']]


def test_parent_rejects_native_coding_identity(tmp_path):
    parent, completion, native = [tmp_path / name for name in ['parent', 'completion', 'native']]
    for folder in [parent, completion, native]:
        folder.mkdir()
    (parent / 'controller.exited.json').write_text('{}')
    (parent / 'archive-lock.json').write_text(json.dumps({'files': seal(parent)}))
    (completion / 'final-audit.json').write_text(json.dumps(dict.fromkeys(
        ['coding_model_calls', 'proposer_calls', 'official_grader_calls', 'fresh_coding_scores'], 0)))
    (completion / 'archive-lock.json').write_text(json.dumps({'files': seal(completion)}))
    (native / 'trial-1').mkdir()
    with pytest.raises(HXError, match='consumed native'):
        recovery.stopped_zero_model_parent(parent, completion, native)
