import io
import json
import tarfile
from types import SimpleNamespace

import pytest

from benchmarks.polybench.sessions import TaskSessions, codex_arguments, history_files
from hx.models import GateError, Task
from hx.usage import usage_breakdown
from scripts.report_worker_usage import report

IDENTIFIER = '126ac8c2-c0c6-43bd-9a0d-251915009c3c'


def packed(name, data=b'{}\n', kind=tarfile.REGTYPE):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tar:
        item = tarfile.TarInfo(name)
        item.size = len(data) if kind == tarfile.REGTYPE else 0
        item.type = kind
        tar.addfile(item, io.BytesIO(data) if item.size else None)
    return [stream.getvalue()]


def test_usage_cached_input_is_subset_and_unknown_is_explicit():
    actual = usage_breakdown({'input_tokens': 100, 'output_tokens': 20, 'cached_input_tokens': 80})
    assert actual['reported_tokens'] == 120
    assert actual['uncached_input_tokens'] == 20
    assert actual['monetary_cost'] is None
    assert usage_breakdown({})['reported_tokens'] is None
    assert usage_breakdown({'input_tokens': True})['input_tokens'] is None
    assert usage_breakdown({'input_tokens': 2, 'cached_input_tokens': 3})['cache_usage_known'] is False


@pytest.mark.parametrize('name,kind', [
    ('../auth.json', tarfile.REGTYPE), ('sessions/auth.json', tarfile.REGTYPE),
    ('/sessions/a.jsonl', tarfile.REGTYPE), ('sessions/link', tarfile.SYMTYPE),
    ('sessions/foreign-00000000-0000-0000-0000-000000000000.jsonl', tarfile.REGTYPE),
])
def test_native_history_rejects_foreign_paths_secrets_and_links(name, kind):
    with pytest.raises(GateError):
        history_files(packed(name, kind=kind), IDENTIFIER)


def test_native_rollout_repacked_without_credentials():
    name = 'sessions/2026/10/05/rollout-date-' + IDENTIFIER + '.jsonl'
    assert history_files(packed(name), IDENTIFIER) == {name: b'{}\n'}


def test_sessions_isolate_task_run_model_schema_and_exact_source():
    task = Task(id='one', repo='repo', report='Fix something', kind='bug')
    sessions = TaskSessions()
    key = sessions.key('run1', task, 'model', {}, '/testbed')
    sessions.save(key, IDENTIFIER, 'tree1', {'file': b'log'})
    assert sessions.get(key, 'tree1').identifier == IDENTIFIER
    for foreign in [sessions.key('run2', task, 'model', {}, '/testbed'),
                    sessions.key('run1', task.model_copy(update={'id': 'two'}), 'model', {}, '/testbed'),
                    sessions.key('run1', task, 'different', {}, '/testbed'),
                    sessions.key('run1', task, 'model', {'changed': True}, '/testbed')]:
        assert sessions.get(foreign, 'tree1') is None
    with pytest.raises(GateError, match='source differs'):
        sessions.get(key, 'different_tree')
    sessions.invalidate(key)
    assert sessions.get(key, 'tree1') is None


def test_resume_flags_target_explicit_session_and_preserve_schema():
    argv = codex_arguments('model', 'workspace-write', 'medium', '/testbed', IDENTIFIER, True)
    assert argv[3] == 'resume'
    assert '--last' not in argv and '--ephemeral' not in argv
    assert '--sandbox' not in argv and '-C' not in argv
    assert argv[-2:] == [IDENTIFIER, '-']
    assert '--output-schema' in argv and 'sandbox_mode="workspace-write"' in argv
    assert '--ephemeral' in codex_arguments('model', 'read-only', 'medium', '/testbed')


def test_usage_report_splits_author_implementation_and_repair(tmp_path):
    for step, count in [('independent_challenge', 10), ('implement', 20), ('revise_1', 30)]:
        path = tmp_path / f'tasks/task/experiments/heldout-results/trial/state/runs/run/steps/{step}/attempt-1/delegate-0/stdout.txt'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'type': 'turn.completed', 'usage': {
            'input_tokens': count, 'output_tokens': 1, 'cached_input_tokens': 5}}) + '\n')
    result = report(tmp_path)
    assert result['roles']['test_author']['reported_tokens'] == 11
    assert result['roles']['implementer']['reported_tokens'] == 21
    assert result['roles']['repair']['reported_tokens'] == 31


def test_container_resume_uses_saved_history_and_invalidates_failed_continuation(tmp_path, monkeypatch):
    from benchmarks.polybench import containers as module
    from hx.models import Settings, WorkerSummary
    task = Task(id='one', repo=str(tmp_path), report='Fix public behavior', kind='bug')
    settings = Settings(adapter='fake', workflow='single')
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    adapter = module.ContainerAdapter(settings, None,
        {'repo': 'fixture', 'upstream_base': 'base', 'image_id': 'fixture-image'}, None, auth)
    adapter.sessions = TaskSessions()
    name = 'sessions/2026/10/05/rollout-date-' + IDENTIFIER + '.jsonl'
    uploads, launches, removed = [], [], []
    container = SimpleNamespace(id='container', put_archive=lambda path, data: uploads.append((path, data)),
        get_archive=lambda path: (packed(name), {}), remove=lambda **kw: removed.append(True))
    monkeypatch.setattr(module, 'create', lambda *a: (container, '/testbed'))
    monkeypatch.setattr(module, 'prepare_dependencies', lambda *a: None)
    monkeypatch.setattr(module, 'share_public_fixture', lambda *a: None)
    monkeypatch.setattr(module, 'populate', lambda *a: 'head')
    monkeypatch.setattr(module, 'build_check', lambda *a: None)
    monkeypatch.setattr(module, 'recipe', lambda *a: None)
    monkeypatch.setattr(module, 'git', lambda *a: 'tree')
    def command(_container, argv, *args, **kwargs):
        if argv == ['git', 'rev-parse', 'HEAD']:
            return b'head'
        if argv == ['git', 'write-tree']:
            return b'tree'
        if argv[:2] == ['sh', '-c']:
            return b'/usr/bin/python' if 'python3' in argv[2] and 'for tool' not in argv[2] else b'git=/usr/bin/git\n'
        return b''
    monkeypatch.setattr(module, 'command', command)
    result = {'summary': 'Done', 'tests_added': [], 'limitations': [], 'verification_commands': []}
    monkeypatch.setattr(module, 'read_file', lambda *a: json.dumps(result).encode())
    def execute(argv, cwd, env, log, timeout, control, on_line, prompt, limit):
        launches.append((argv, prompt))
        on_line(json.dumps({'type': 'thread.started', 'thread_id': IDENTIFIER}))
        on_line(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 2}}))
        return 0, '', ''
    monkeypatch.setattr(module, 'execute', execute)
    events = []
    for index in range(2):
        log = tmp_path / str(index)
        log.mkdir()
        adapter.run('implementer', task, tmp_path,
            {'native_session_scope': 'run1', 'native_session_continuation': index == 1,
             'repair_plan': {'instruction': 'repair observed failure'}},
            'original instructions', WorkerSummary, log, lambda: None,
            lambda name, data: events.append((name, data)), 30)
    assert '--ephemeral' not in launches[0][0]
    assert 'resume' in launches[1][0] and IDENTIFIER in launches[1][0]
    assert 'original instructions' not in launches[1][1]
    assert 'repair observed failure' in launches[1][1]
    assert len(removed) == 2
    assert [data['resumed'] for name, data in events if name == 'worker.session'] == [False, True]
    assert (tmp_path / '1/native-history' / name).exists()
    assert not (tmp_path / '1/native-history/auth.json').exists()
    def fail(*args):
        raise RuntimeError('interrupted model call')
    monkeypatch.setattr(module, 'execute', fail)
    monkeypatch.setattr(module, 'retain_interrupted_draft', lambda *a: None)
    log = tmp_path / 'fail'
    log.mkdir()
    with pytest.raises(RuntimeError):
        adapter.run('implementer', task, tmp_path, {'native_session_scope': 'run1'},
            'instructions', WorkerSummary, log, lambda: None, lambda *a: None, 30)
    assert not adapter.sessions.histories


def test_lean_replay_preserves_original_tests_and_exact_production(tmp_path):
    from pathlib import Path

    from benchmarks.polybench.delivery import production_patch
    from benchmarks.polybench.lean import prepare_lean_replay
    from hx.git import clone, derive, git
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init')
    git(repo, 'config', 'user.name', 'HX fixture')
    git(repo, 'config', 'user.email', 'fixture@hx.test')
    (repo / 'source.py').write_text('value = 0\n')
    (repo / 'tests').mkdir()
    (repo / 'tests/test_original.py').write_text('assert value == 0\n')
    git(repo, 'add', '--all')
    git(repo, 'commit', '-m', 'base')
    base = git(repo, 'rev-parse', 'HEAD')
    task = Task(id='lean-test', repo=str(repo), report='Fix incorrect value', base_commit=base,
                allowed_paths=['**'], protected_paths=['__private/**'])
    (repo / 'source.py').write_text('value = 1\n')
    (repo / 'tests/test_original.py').write_text('assert True\n')
    (repo / 'tests/test_added.py').write_text('assert value == 1\n')
    candidate = derive(repo, base, base, task).model_copy(update={
        'verification_commands': [['pytest', '-vv', 'tests']]})
    overlay = prepare_lean_replay(candidate, task, tmp_path / 'replay', clone)
    workspace = Path(overlay.workspace)
    assert (workspace / 'source.py').read_text() == 'value = 1\n'
    assert (workspace / 'tests/test_original.py').read_text() == 'assert value == 0\n'
    assert (workspace / 'tests/test_added.py').read_text() == 'assert value == 1\n'
    assert production_patch(overlay)[0] == production_patch(candidate)[0]
    assert (repo / 'tests/test_original.py').read_text() == 'assert True\n'
    receipt = json.loads((tmp_path / 'replay/lean-delivery.json').read_text())
    assert receipt['existing_test_edits_inherited'] is False


def test_lean_worker_instructs_new_regressions_before_native_continuation(monkeypatch):
    from benchmarks.polybench.engine import PolyEngine
    from benchmarks.polybench.lean import PUBLIC_REPLAY_CONTRACT, LeanEngine
    calls = []
    monkeypatch.setattr(PolyEngine, '_worker', lambda self, *args: calls.append(args[5]))
    engine = object.__new__(LeanEngine)
    engine._worker('run', 'implement_0', None, None, None, {}, None, None, None)
    engine._worker('run', 'revise_1', None, None, None, {}, None, None, None)
    assert calls[0]['public_replay_contract'] == PUBLIC_REPLAY_CONTRACT
    assert 'NEW conventional test files' in PUBLIC_REPLAY_CONTRACT
    assert 'named' in PUBLIC_REPLAY_CONTRACT and 'original source' in PUBLIC_REPLAY_CONTRACT
    assert calls[1]['native_session_continuation'] is True
    assert 'public_replay_contract' not in calls[1]  # retained in task-local native history


def test_startup_recovery_cannot_replace_consumed_coding_identity(tmp_path):
    import sqlite3

    from benchmarks.polybench.prepare import sha
    from scripts.run_lean_development import inherited_startup
    parent = tmp_path / 'parent'
    parent.mkdir()
    (parent / 'plan.json').write_text(json.dumps({'started': 10, 'deadline': 1810}))
    (parent / 'plan.lock.json').write_text(json.dumps({'sha256': sha(parent / 'plan.json')}))
    (parent / 'controller.exited.json').write_text('{}')
    (parent / 'stop.json').write_text('{}')
    state = parent / 'experiments/heldout-results/trial/state'
    state.mkdir(parents=True)
    native = tmp_path / 'native'
    native.mkdir()
    (state / 'native-state.json').write_text(json.dumps({'root': str(native)}))
    with sqlite3.connect(native / 'state.sqlite3') as conn:
        conn.execute('CREATE TABLE runs (id TEXT)')
    record = inherited_startup(parent)
    assert record['coding_identities'] == 0 and record['plan']['deadline'] == 1810
    with sqlite3.connect(native / 'state.sqlite3') as conn:
        conn.execute("INSERT INTO runs VALUES ('consumed')")
    with pytest.raises(RuntimeError, match='Interrupted coding identity'):
        inherited_startup(parent)
