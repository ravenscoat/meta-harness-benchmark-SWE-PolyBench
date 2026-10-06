"""Worker-loop surface of the existing code-search command.

One isolated Sol proposal, real fixture execution and sealed compatibility gates.
Passing these gates makes a candidate eligible for task experiments, never an
automatic coding-performance promotion.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench.runner import AUTH, BINARY
from hx.code_search import CodeProposal, copy_experience, seal, sha
from hx.config import canonical, digest, load_settings
from hx.git import git
from hx.models import HXError, Task
from hx.process import clean_env
from hx.store import atomic_write
from hx.worker_scaffold import TARGET, VERSION, validate_scaffold
from scripts.overnight_limits import account_usage, can_start

GATES = ['tests/test_worker_scaffold.py', 'tests/test_code_search.py',
         'tests/test_candidate_budget.py', 'tests/test_polybench_public_checks.py']


def runtime_fingerprints(project):
    files = list((project / 'src/hx').glob('*.py')) + list((project / 'src/hx/scaffolds').glob('*.py'))
    files += list((project / 'benchmarks/polybench').glob('*.py'))
    files += [project / name for name in GATES + ['tests/conftest.py', 'tests/test_worker_environment.py',
              'scripts/run_code_search.py', 'scripts/worker_scaffold_search.py',
              'scripts/recover_worker_scaffold.py', 'scripts/overnight_limits.py']]
    return {str(p): sha(p.read_bytes()) for p in files}


def verified_archive(search):
    archive = json.loads((search / 'archive-lock.json').read_text())['files']
    if {k: v for k, v in seal(search).items() if k != 'archive-lock.json'} != archive:
        raise HXError('Search archive changed')
    return archive


def exported_public_sources(project):
    # Explicit full PUBLIC worker logs only. No grader folders, accepted patches,
    # credentials, effective configs, final evaluation roots or recursive export.
    trial = project / '.hx/independent-three-v2/experiments/heldout-results/full-serverless__serverless-7374-1'
    step = trial / 'state/runs/r-024636e715574df0/steps/independent_challenge/attempt-1'
    return {'consumed-command-failure/' + name: step / name
            for name in ('prompt.txt', 'stdout.txt', 'stderr.txt') if (step / name).is_file()}


def exercise_scaffold(source, directory):
    """Real FastAPI fixture tests and verification with a scripted worker.

    This proves executable integration and integrity, not model coding quality.
    All worker usage in this exercise is simulated, not paid model usage.
    """
    from hx.adapters import FakeAdapter
    from hx.config import load_task
    from hx.demo import initialize
    from hx.engine import Engine
    from hx.models import Settings
    from hx.store import Store
    from hx.worker_scaffold import WorkerScaffoldAdapter

    tasks = initialize(directory / 'repository')
    task = next(load_task(path) for path in tasks if path.stem == 'missing-task')
    settings = Settings(adapter='fake', workflow='single', max_attempts=1, max_revisions=0)
    delegate = FakeAdapter()
    store = Store(directory / 'state')
    engine = Engine(store, settings, delegate)
    engine.adapter = WorkerScaffoldAdapter(delegate, source, settings)
    engine.config['worker_scaffold'] = {'version': VERSION, 'sha256': engine.adapter.planner.sha256}
    engine.config['fingerprint'] = digest({k: v for k, v in engine.config.items() if k != 'fingerprint'})
    run = engine.create(task)
    result = engine.execute(run['id'])
    atomic_write(directory / 'result.json', canonical({
        'status': result['status'], 'error': result['error'], 'handoff': result.get('handoff'),
        'delegate_calls': delegate.calls, 'events': store.events(run['id']),
        'limitation': 'Scripted worker and real fixture checks; not a model task-resolution score.'}))
    return result['status'] == 'ready_for_approval' and result['handoff']['verified']


def select_for_experiment(experiment, search):
    """Select a gate-passing candidate before locking a NEW experiment root."""
    if (experiment / 'experiments/source-lock.json').exists() or (experiment / 'worker-scaffold.py').exists():
        raise HXError('Scaffold selection requires an unfrozen experiment without an incumbent scaffold')
    verified_archive(search)
    readiness = json.loads((search / 'candidate-ready.json').read_text())
    candidate = search / 'candidate.py'
    if not readiness['eligible_for_task_experiment'] or sha(candidate.read_bytes()) != readiness['sha256']:
        raise HXError('Scaffold lacks compatibility evidence')
    runtime = readiness.get('runtime_files')
    if not runtime or not all(sha(Path(p).read_bytes()) == value for p, value in runtime.items()):
        raise HXError('Scaffold requires validation against the current controller runtime')
    validate_scaffold(candidate.read_bytes())
    experiment.mkdir(parents=True, exist_ok=True)
    atomic_write(experiment / 'worker-scaffold.py', candidate.read_bytes())
    atomic_write(experiment / 'worker-scaffold.lock.json', canonical({
        'sha256': readiness['sha256'], 'search_archive_sha256': sha((search / 'archive-lock.json').read_bytes()),
        'coding_performance_promoted': False, 'classification': 'Experimental candidate, not a demonstrated improvement'}))


def run(root, history):
    project = Path.cwd().resolve()
    root = Path(root).resolve()
    if root.exists():
        raise HXError('New worker-search identity required')
    # One search/evaluation controller at a time, across existing experiment types.
    with FileLock(str(project / '.hx/single-evaluation-controller.lock'), timeout=0):
        root.mkdir(parents=True)
        usage, completed = 0, False
        started = time.monotonic()
        originals = {str(p): sha(p.read_bytes()) for p in project.glob('.hx/*/experiments/*/*/score.json')}
        runtime = runtime_fingerprints(project)
        try:
            quota = account_usage(BINARY, AUTH)
            atomic_write(root / 'quota.json', canonical(quota))
            if not can_start(quota):
                raise HXError('Account quota does not permit proposal; no reset credits redeemed')
            with tempfile.TemporaryDirectory(prefix='hx-loop-search-',
                    dir='/opt/hx-polybench-runtime/v1/infra-checks') as temporary:
                native = Path(temporary)
                workspace = native / 'workspace'
                workspace.mkdir()
                baseline = (project / 'src/hx/scaffolds/single_call.py').read_bytes()
                atomic_write(workspace / TARGET, baseline)
                atomic_write(root / 'incumbent.py', baseline)
                copy_experience(workspace / 'experience', exported_public_sources(project))
                copy_experience(root / 'experience', exported_public_sources(project))
                # Read-only implementation/interface reference; proposer may change
                # only candidate_scaffold.py, not this trusted controller or tests.
                references = {name: project / name for name in
                    ['src/hx/worker_scaffold.py', 'src/hx/models.py', 'src/hx/scaffolds/single_call.py',
                     'benchmarks/polybench/public_checks.py']}
                copy_experience(workspace / 'reference', references)
                for index, old in enumerate(history):
                    archive = json.loads((old / 'archive-lock.json').read_text())['files']
                    actual = {k: v for k, v in seal(old).items() if k != 'archive-lock.json'}
                    if archive != actual:
                        raise HXError('Prior candidate archive changed')
                    selected = {name: old / name for name in archive if name in
                        {'candidate.py', 'incumbent.py', 'proposal.json', 'failure.json', 'candidate-ready.json'}
                        or name.startswith(('sol/', 'experience/'))}
                    copy_experience(workspace / 'history' / str(index), selected)
                git(workspace, 'init')
                git(workspace, 'add', '.')
                git(workspace, '-c', 'user.name=HX', '-c', 'user.email=hx@local', 'commit', '-qm', 'Search incumbent')
                before = {n: h for n, h in seal(workspace).items() if not n.startswith('.git/')}
                instructions = (
                    'You are Sol, the coding meta-harness optimizer. Read reference/, experience/ and history/. '
                    'The exported failed evaluation task is now CONSUMED DEVELOPMENT experience, not heldout. '
                    'Write ONE executable worker-loop candidate in candidate_scaffold.py. Keep next_action(state). '
                    'It chooses inspect/delegate/finish actions, optional source-context selection and bounded '
                    'memory/context/guidance. Read the controller and Action schema. Every action must supply '
                    'all six properties. Only this file may change. One failure-driven mechanism per candidate: '
                    'improve useful orientation/context construction before delegating, avoiding redundant worker '
                    'calls and duplicated context. Existing workflow contracts and verification cannot be dropped. '
                    'Do not hardcode task names, issue solutions, fixture answers or benchmark-specific branches. '
                    'Generalize from the command/contract failure. Only import re; use pure functions and normal '
                    'string/list/dict operations. No IO, dynamic code, reflection, decorators or host capabilities. '
                    'Do not execute Python/tests/models/network or modify Git history. Read/edit only; the external '
                    'controller will execute compatibility and real fixture checks after your turn. '
                    'Return diagnosis, inspected_files (existing relative files you actually read), change and limitations. '
                    'Do not claim coding improvement based on smoke checks.')
                atomic_write(root / 'plan.json', canonical({'surface': 'worker-loop', 'version': VERSION,
                    'proposer_model': 'gpt-6.1-sol', 'proposal_token_target': 60000,
                    'proposal_seconds': 180, 'max_proposals': 1, 'automatic_promotion': False,
                    'historical_scores': originals, 'runtime_files': runtime, 'instructions': instructions}))
                def control():
                    if time.monotonic() - started > 300 or usage >= 60000:
                        raise HXError('Worker scaffold proposal envelope exhausted')
                def emit(kind, data):
                    nonlocal usage
                    if kind == 'worker.usage':
                        usage += int(data['tokens'])
                    with (root / 'events.jsonl').open('ab') as stream:
                        stream.write(canonical({'kind': kind, 'data': data}) + b'\n')
                    atomic_write(root / 'usage.json', canonical({'reported_tokens': usage,
                        'target': 60000, 'usage_known': completed}))
                settings = load_settings(project / 'hx.toml').model_copy(update={'worker_model': 'gpt-6.1-sol'})
                # The optimizer gets an isolated container with supplied public
                # files, not the host experiment tree or private grading inputs.
                # Reuse a cached dependency image as a carrier; no coding task is
                # run against it and its original benchmark source is replaced.
                import docker

                from benchmarks.polybench.containers import ContainerAdapter
                case = json.loads((project / '.hx/independent-three-v2/images.json').read_text())['mui__material-ui-28190']
                case = {**case, 'repo': 'hx/worker-scaffold', 'repo_path': str(workspace)}
                client = docker.from_env(timeout=180)
                try:
                    client.images.get(case['image_id'])
                    raw = ContainerAdapter(settings, client, case, BINARY, AUTH).run('implementer', Task(id='worker-scaffold-search', repo=str(workspace),
                        report='Improve the executable worker loop from public command/contract failure evidence.'),
                        workspace, {'editable_source': TARGET, 'worker_model_unchanged': True}, instructions,
                        CodeProposal, root / 'sol', control, emit, 180)
                    completed = True
                finally:
                    client.close()
                atomic_write(root / 'usage.json', canonical({'reported_tokens': usage, 'usage_known': completed}))
                atomic_write(root / 'proposal.json', canonical(CodeProposal.model_validate(raw).model_dump()))
                after = {n: h for n, h in seal(workspace).items() if not n.startswith('.git/')}
                changed = {n for n in set(before) | set(after) if before.get(n) != after.get(n)}
                candidate = (workspace / TARGET).read_bytes()
                atomic_write(root / 'candidate.py', candidate)
                if changed != {TARGET} or git(workspace, 'remote'):
                    raise HXError('Candidate changed protected inputs, added a remote, or made no change')
                if not all(name in before for name in raw['inspected_files']):
                    raise HXError('Proposal names unknown evidence files')
                validate_scaffold(candidate)
                # The proposer cannot see fixture/evaluator output during its turn.
                fixture = exercise_scaffold(root / 'candidate.py', native / 'fixture')
                shutil.copytree(native / 'fixture', root / 'fixture', ignore=shutil.ignore_patterns('__pycache__'))
                gates = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                    *GATES, '--basetemp=' + str(native / 'gates')], capture_output=True, timeout=180,
                    env=clean_env())
                atomic_write(root / 'gates.stdout.txt', gates.stdout)
                atomic_write(root / 'gates.stderr.txt', gates.stderr)
                atomic_write(root / 'candidate-ready.json', canonical({
                    'eligible_for_task_experiment': fixture and gates.returncode == 0,
                    'sha256': sha(candidate), 'real_fixture_verified': fixture,
                    'regressions_passed': gates.returncode == 0, 'coding_performance_promoted': False,
                    'runtime_files': runtime,
                    'reported_tokens': usage, 'usage_known': completed,
                    'limitations': 'One Sol code proposal. No model coding tasks or official resolution measured. '
                                   'Real checks use scripted worker; task evidence is required for promotion.'}))
        except Exception as error:
            atomic_write(root / 'failure.json', canonical({'error': str(error), 'reported_tokens': usage,
                'usage_known': completed, 'coding_performance_promoted': False}))
            raise
        finally:
            unchanged = all(sha(Path(p).read_bytes()) == value for p, value in originals.items())
            atomic_write(root / 'integrity.json', canonical({'historical_scores_unchanged': unchanged,
                'runtime_unchanged': all(sha(Path(p).read_bytes()) == value for p, value in runtime.items()),
                'count': len(originals), 'seconds': time.monotonic() - started}))
            atomic_write(root / 'archive-lock.json', canonical({'files': seal(root)}))


def finalize_recovered_candidate(search, root):
    """Zero-model validation against the final controller, preserving parent archives."""
    project = Path.cwd().resolve()
    search, root = search.resolve(), root.resolve()
    verified_archive(search)
    if root.exists():
        raise HXError('New compatibility identity required')
    with FileLock(str(project / '.hx/single-evaluation-controller.lock'), timeout=0):
        root.mkdir(parents=True)
        runtime = runtime_fingerprints(project)
        scores = {str(p): sha(p.read_bytes()) for p in project.glob('.hx/*/experiments/*/*/score.json')}
        parent_sha = sha((search / 'archive-lock.json').read_bytes())
        try:
            candidate = (search / 'candidate.py').read_bytes()
            validate_scaffold(candidate)
            atomic_write(root / 'candidate.py', candidate)
            atomic_write(root / 'plan.json', canonical({'model_calls': 0, 'parent': str(search),
                'parent_archive_sha256': parent_sha, 'runtime_files': runtime, 'historical_scores': scores}))
            snapshot = root / 'runtime-source'
            for path in runtime:
                destination = snapshot / Path(path).relative_to(project)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
            with tempfile.TemporaryDirectory(prefix='hx-loop-final-gates-',
                    dir='/opt/hx-polybench-runtime/v1/infra-checks') as temporary:
                native = Path(temporary)
                fixture = exercise_scaffold(root / 'candidate.py', native / 'fixture')
                shutil.copytree(native / 'fixture', root / 'fixture', ignore=shutil.ignore_patterns('__pycache__'))
                result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                    *GATES, 'tests/test_worker_environment.py', '--basetemp=' + str(native / 'gates')],
                    capture_output=True, timeout=180, env=clean_env())
                atomic_write(root / 'gates.stdout.txt', result.stdout)
                atomic_write(root / 'gates.stderr.txt', result.stderr)
            unchanged = all(sha(Path(p).read_bytes()) == value for p, value in {**runtime, **scores}.items())
            if not unchanged or sha((search / 'archive-lock.json').read_bytes()) != parent_sha:
                raise HXError('Runtime or sealed evidence changed during final compatibility checks')
            atomic_write(root / 'candidate-ready.json', canonical({'eligible_for_task_experiment':
                fixture and result.returncode == 0, 'sha256': sha(candidate), 'runtime_files': runtime,
                'real_fixture_verified': fixture, 'regressions_passed': result.returncode == 0,
                'model_calls': 0, 'historical_scores_unchanged': len(scores),
                'coding_performance_promoted': False,
                'limitations': 'Compatibility gates plus scripted-worker fixture only. Parent budget failure '
                               'is preserved; no model coding accuracy or official grading measured.'}))
        except Exception as error:
            atomic_write(root / 'failure.json', canonical({'error': str(error), 'model_calls': 0}))
            raise
        finally:
            atomic_write(root / 'archive-lock.json', canonical({'files': seal(root)}))


if __name__ == '__main__':
    raise SystemExit('Use scripts.run_code_search --surface worker-loop ROOT')
