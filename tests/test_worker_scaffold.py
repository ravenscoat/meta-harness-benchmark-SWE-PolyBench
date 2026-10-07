from pathlib import Path

import pytest

from hx.models import HXError, ProcessTimeout, Settings, Task, WorkerSummary
from hx.worker_scaffold import Planner, WorkerScaffoldAdapter, validate_scaffold

BASE = Path(__file__).parents[1] / 'src/hx/scaffolds/single_call.py'


def source(tmp_path, body):
    path = tmp_path / 'candidate.py'
    path.write_text('def next_action(state):\n' + body)
    return path


def action(kind, **extras):
    return {'action': kind, 'query': '', 'guidance': '', 'memory': {}, 'context': {},
            'omit_optional_context': [], **extras}


class Delegate:
    capabilities = {'streaming': True}

    def __init__(self):
        self.calls = []

    def run(self, role, task, workspace, context, instructions, contract, directory, control, emit, timeout):
        self.calls.append((role, context, instructions, timeout))
        emit('worker.usage', {'tokens': 17})
        return {'summary': 'Worker completed a real schema result.', 'tests_added': [], 'limitations': [],
                'verification_commands': [['pytest', 'tests/test_behavior.py']]}


def execute(tmp_path, scaffold=BASE, context=None, timeout=30, control=lambda: None):
    delegate = Delegate()
    wrapped = WorkerScaffoldAdapter(delegate, scaffold, Settings())
    task = Task(id='scaffold-test', repo=str(tmp_path), report='Fix the public behavior')
    events = []
    result = wrapped.run('implementer', task, tmp_path, context or {}, 'FIXED CONTRACT', WorkerSummary,
        tmp_path / 'run', control, lambda event, data: events.append((event, data)), timeout)
    return result, delegate, events


def test_incumbent_delegates_once_preserves_contract_and_usage(tmp_path):
    result, delegate, events = execute(tmp_path, context={'verification_contract': 'IMMUTABLE'})
    assert len(delegate.calls) == 1
    assert delegate.calls[0][1]['verification_contract'] == 'IMMUTABLE'
    assert delegate.calls[0][2] == 'FIXED CONTRACT'
    assert 0 < delegate.calls[0][3] < 30
    assert result['verification_commands'] == [['pytest', 'tests/test_behavior.py']]
    assert sum(data['tokens'] for kind, data in events if kind == 'worker.usage') == 17
    assert (tmp_path / 'run/result.json').exists()


def test_candidate_changes_worker_loop_and_context_instead_of_numeric_knob(tmp_path):
    path = source(tmp_path, "    return " + repr(action('delegate', context={'diagnosis': 'Trace lifecycle'},
        omit_optional_context=['tracked_files_prefix'])) + " if state['worker_calls'] < 2 else " + repr(action('finish')))
    _, delegate, events = execute(tmp_path, path, {'tracked_files_prefix': 'OPTIONAL', 'verification_contract': 'KEEP'})
    assert len(delegate.calls) == 2
    assert all('tracked_files_prefix' not in call[1] for call in delegate.calls)
    assert all(call[1]['verification_contract'] == 'KEEP' for call in delegate.calls)
    assert delegate.calls[1][1]['executable_scaffold']['previous_summary'] is not None
    assert sum(data['tokens'] for kind, data in events if kind == 'worker.usage') == 34


def test_real_public_repository_inspection_runs_before_delegate(tmp_path):
    from hx.git import git
    (tmp_path / 'source.py').write_text('def lifecycle():\n    return 1\n')
    git(tmp_path, 'init')
    git(tmp_path, 'add', 'source.py')
    path = source(tmp_path, "    if not state['inspections']:\n        return " +
        repr(action('inspect', query='lifecycle')) + "\n    return " + repr(action('delegate')) +
        " if not state['worker_calls'] else " + repr(action('finish')))
    _, delegate, _ = execute(tmp_path, path)
    assert delegate.calls[0][1]['executable_scaffold']['observations'][0]['matches'][0]['path'] == 'source.py'
    assert (tmp_path / 'source.py').read_text() == 'def lifecycle():\n    return 1\n'


@pytest.mark.parametrize('kind', ['finish', 'unsupported'])
def test_cannot_bypass_worker_or_choose_unknown_action(tmp_path, kind):
    path = source(tmp_path, '    return ' + repr(action(kind)))
    with pytest.raises(HXError):
        execute(tmp_path, path)


def test_cannot_drop_verification_contract(tmp_path):
    path = source(tmp_path, '    return ' + repr(action('delegate', omit_optional_context=['verification_contract'])))
    with pytest.raises(HXError, match='invalid action'):
        execute(tmp_path, path)


def test_delegate_budget_and_model_headroom_enforced(tmp_path):
    path = source(tmp_path, '    return ' + repr(action('delegate')))
    with pytest.raises(HXError, match='delegate-call limit'):
        execute(tmp_path, path)
    delegate = Delegate()
    wrapped = WorkerScaffoldAdapter(delegate, BASE, Settings(repair_token_reserve=5000))
    wrapped.headroom = lambda: 4999
    with pytest.raises(HXError, match='headroom'):
        wrapped.run('implementer', Task(id='x', repo=str(tmp_path), report='Public issue'), tmp_path,
            {}, 'FIXED', WorkerSummary, tmp_path / 'quota-run', lambda: None, lambda *a: None, 30)
    assert delegate.calls == []


def test_deadline_and_cancellation_are_shared_not_reset(tmp_path):
    with pytest.raises(ProcessTimeout):
        execute(tmp_path, timeout=0)
    def cancelled():
        raise HXError('operator stop')
    with pytest.raises(HXError, match='operator stop'):
        execute(tmp_path, control=cancelled)


def test_budget_exhaustion_preserves_first_result_without_another_call(tmp_path):
    path = source(tmp_path, '    return ' + repr(action('delegate')) +
        " if state['worker_calls'] < 2 else " + repr(action('finish')))
    delegate = Delegate()
    wrapped = WorkerScaffoldAdapter(delegate, path, Settings(repair_token_reserve=5000))
    wrapped.headroom = lambda: 5000 if not delegate.calls else 4999
    events = []
    result = wrapped.run('implementer', Task(id='x', repo=str(tmp_path), report='Fix behavior'),
        tmp_path, {}, 'FIXED', WorkerSummary, tmp_path/'budget-run', lambda: None,
        lambda kind, data: events.append((kind, data)), 30)
    assert len(delegate.calls) == 1
    assert result['verification_commands'] == [['pytest', 'tests/test_behavior.py']]
    assert any(kind == 'scaffold.check_skipped' and data['candidate_preserved']
               for kind,data in events)
    assert (tmp_path/'budget-run/result.json').exists()


def test_candidate_mutation_after_fingerprint_rejected(tmp_path):
    path = source(tmp_path, '    return ' + repr(action('delegate')))
    planner = Planner(path)
    path.write_text(path.read_text() + '\n# changed')
    with pytest.raises(HXError, match='changed'):
        planner.decide({}, tmp_path / 'decision')


@pytest.mark.parametrize('code', ['import os\ndef next_action(state): return {}',
    'def next_action(state): return open("auth.json").read()',
    'def next_action(other): return {}', 'def next_action(state,*args): return {}'])
def test_candidate_interface_cannot_import_host_capabilities(code):
    with pytest.raises(HXError):
        validate_scaffold(code.encode())


def test_decision_subprocess_does_not_inherit_auth(tmp_path, monkeypatch):
    import hx.worker_scaffold as module
    original = module.subprocess.run
    observed = []
    def run(*args, **kwargs):
        observed.append(kwargs['env'])
        return original(*args, **kwargs)
    monkeypatch.setenv('CODEX_HOME', 'private-auth')
    monkeypatch.setattr(module.subprocess, 'run', run)
    Planner(BASE).decide({'worker_calls': 0}, tmp_path / 'decision')
    assert 'CODEX_HOME' not in observed[0]


def test_verification_still_blocks_after_scaffold_worker(project, setup_engine, tmp_path):
    from hx.models import Check, Verification
    engine, fake = setup_engine(workflow='single')
    engine.adapter = WorkerScaffoldAdapter(fake, BASE, engine.settings)
    class FailedVerifier:
        def run(self, candidate, *args):
            return Verification(candidate_commit=candidate.candidate_commit, passed=False,
                checks=[Check(name='behavior', passed=False, evidence='Actual failed assertion')],
                changed_line_coverage=None, known_gaps=[])
    engine.verifier = FailedVerifier()
    run = engine.create(project['missing-task'])
    result = engine.execute(run['id'])
    assert result['status'] == 'needs_attention', result['error']
    assert not result['handoff']['verified']


def test_scaffold_completes_real_fastapi_workflow(project, setup_engine):
    engine, fake = setup_engine(workflow='single')
    engine.adapter = WorkerScaffoldAdapter(fake, BASE, engine.settings)
    run = engine.create(project['missing-task'])
    result = engine.execute(run['id'])
    assert result['status'] == 'ready_for_approval', result['error']
    assert result['handoff']['verified']
    assert fake.calls == {'implementer': 1}
    assert any(e['type'] == 'scaffold.action' for e in engine.store.events(run['id']))


def test_logged_recovery_requires_complete_exact_file_output(tmp_path):
    import json

    from scripts.recover_worker_scaffold import logged_source
    trace = tmp_path / 'stdout.txt'
    trace.write_text(json.dumps({'item': {'type': 'command_execution', 'status': 'completed',
        'exit_code': 0, 'command': "/bin/bash -lc 'cat candidate_scaffold.py'",
        'aggregated_output': BASE.read_text()}}) + '\n')
    assert logged_source(trace) == BASE.read_bytes()
    trace.write_text(json.dumps({'item': {'type': 'command_execution', 'status': 'started',
        'command': "/bin/bash -lc 'cat candidate_scaffold.py'", 'aggregated_output': BASE.read_text()}}) + '\n')
    with pytest.raises(HXError, match='No complete'):
        logged_source(trace)


def test_candidate_selection_requires_immutable_archive_and_current_runtime(tmp_path):
    import json

    from hx.code_search import seal, sha
    from scripts.worker_scaffold_search import select_for_experiment
    search = tmp_path / 'search'
    search.mkdir()
    (search / 'candidate.py').write_bytes(BASE.read_bytes())
    controller = tmp_path / 'controller.py'
    controller.write_text('controller version one')
    (search / 'candidate-ready.json').write_text(json.dumps({'eligible_for_task_experiment': True,
        'sha256': sha(BASE.read_bytes()), 'runtime_files': {str(controller): sha(controller.read_bytes())}}))
    (search / 'archive-lock.json').write_text(json.dumps({'files': seal(search)}))
    selected = tmp_path / 'new-experiment'
    select_for_experiment(selected, search)
    assert (selected / 'worker-scaffold.py').read_bytes() == BASE.read_bytes()
    with pytest.raises(HXError, match='unfrozen'):
        select_for_experiment(selected, search)
    controller.write_text('changed controller')
    with pytest.raises(HXError, match='current controller'):
        select_for_experiment(tmp_path / 'other-experiment', search)
    (search / 'candidate.py').write_text('mutated')
    with pytest.raises(HXError, match='archive changed'):
        select_for_experiment(tmp_path / 'third-experiment', search)
