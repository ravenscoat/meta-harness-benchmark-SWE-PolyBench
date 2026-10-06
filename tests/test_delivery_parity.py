from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.polybench import delivery_parity as parity
from hx.models import Check


@pytest.mark.parametrize('test_passed,mutated,expected', [(True, False, True),
    (False, False, False), (True, True, False)])
def test_replays_delivered_sources_with_original_test_manifest(monkeypatch, tmp_path,
                                                              test_passed, mutated, expected):
    operations = []
    trees = iter([b'initial', b'mutated' if mutated else b'initial'])
    container = SimpleNamespace(id='offline', put_archive=lambda *a: True,
                                remove=lambda **kw: operations.append('removed'))
    monkeypatch.setattr(parity, 'create', lambda *a, **kw: (container, '/testbed'))
    monkeypatch.setattr(parity, 'populate', lambda *a: operations.append('populated'))
    monkeypatch.setattr(parity, 'archive', lambda *a, **kw: b'patch')
    monkeypatch.setattr(parity, 'production_patch', lambda c: ('source patch',
        {'included_paths': ['src/main.js'], 'excluded_public_test_paths': ['test/index.js']}))
    def command(_container, argv, *args):
        operations.append(argv)
        if argv[:3] == ['git', 'diff', '--cached']:
            return b'src/main.js\0'
        if argv == ['git', 'write-tree']:
            return next(trees)
        if argv[:2] == ['git', 'rev-parse']:
            return b'initial'
        return b''
    monkeypatch.setattr(parity, 'command', command)
    monkeypatch.setattr(parity, 'build_check', lambda *a: Check(name='build', passed=True, evidence=''))
    def execution(argv, workspace):
        assert workspace == Path('/original-base')
        assert operations.index(['git', 'reset', '--hard', 'base']) < operations.index(
            ['git', 'apply', '--binary', '/tmp/hx-delivered.patch'])
        return argv, {}, []
    monkeypatch.setattr(parity, 'public_test_execution', execution)
    monkeypatch.setattr(parity, 'command_check', lambda *a: Check(name='test', passed=test_passed, evidence='test result'))
    monkeypatch.setattr(parity, 'classify_public_logs', lambda *a: (
        'baseline_passed' if test_passed else 'behavioral_failure', {}))
    candidate = SimpleNamespace(workspace='/full-candidate', base_commit='base', candidate_commit='candidate',
                                verification_commands=[['npm', 'test']])
    result = parity.replay_delivery(candidate, tmp_path, SimpleNamespace(max_log_bytes=1000),
        None, {'repo_path': '/original-base'}, lambda: None, lambda *a: None)
    assert result.passed is expected
    assert operations[-1] == 'removed'
    assert (tmp_path / 'delivery-parity.json').exists()
