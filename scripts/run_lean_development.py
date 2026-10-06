"""One new consumed development identity using the common scorer and lean engine."""
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.lean import LeanEngine
from benchmarks.polybench.prepare import sha, write
from scripts.overnight_limits import account_usage, can_start
from scripts.run_fresh_remaining_benchmark import history

CASE = 'mui__material-ui-36353'


def inherited_startup(parent):
    if parent is None:
        return None
    plan = json.loads((parent / 'plan.json').read_text())
    if sha(parent / 'plan.json') != json.loads((parent / 'plan.lock.json').read_text())['sha256']:
        raise RuntimeError('Parent startup plan changed')
    if not (parent / 'controller.exited.json').exists() or not (parent / 'stop.json').exists():
        raise RuntimeError('Parent startup must be stopped with evidence')
    if list(parent.glob('experiments/heldout-results/*/score.json')):
        raise RuntimeError('Scored identity cannot be replaced')
    for descriptor in parent.glob('experiments/heldout-results/*/state/native-state.json'):
        native = Path(json.loads(descriptor.read_text())['root']) / 'state.sqlite3'
        with sqlite3.connect(native.as_uri() + '?mode=ro', uri=True) as conn:
            if conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]:
                raise RuntimeError('Interrupted coding identity cannot be replaced')
    return {'plan': plan, 'root': str(parent), 'plan_sha256': sha(parent / 'plan.json'),
            'stop_sha256': sha(parent / 'stop.json'), 'model_calls': 0, 'coding_identities': 0}


def run(root, parent=None):
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        inherited = inherited_startup(parent)
        if not runner.BINARY.is_file():
            raise RuntimeError('Pinned Codex executable missing')
        os.environ['PATH'] = str(runner.BINARY.parent) + os.pathsep + os.environ.get('PATH', '')
        if root.exists():
            raise RuntimeError('New lean development root required; never retry an existing identity')
        root.mkdir(parents=True)
        original = Path('.hx/polybench-v1')
        selection = json.loads((original / 'selection.json').read_text())
        images = json.loads((original / 'images.json').read_text())
        # Original metadata remains unchanged; exposure is disclosed separately.
        cases = [c for c in selection['cases'] if c['id'] == CASE]
        if len(cases) != 1:
            raise RuntimeError('Pinned case missing')
        write(root / 'selection.json', {**selection, 'cases': cases})
        write(root / 'images.json', {CASE: images[CASE]})
        for name in ['dataset.csv', 'storage.json', 'public/' + CASE + '.json',
                     'preflight/' + CASE + '/validation.json']:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / name, target)
        (root / 'settings.toml').write_text('''adapter = "codex"
workflow = "single"
worker_model = "gpt-6.1-sol"
judgment_model = "gpt-6.1-sol"
reasoning_effort = "medium"
max_attempts = 1
max_revisions = 1
repair_token_reserve = 40000
max_observed_tokens = 200000
attempt_timeout_seconds = 600
verification_timeout_seconds = 180
run_timeout_seconds = 1200
max_log_bytes = 20000000
''')
        (root / 'experiments').mkdir()
        runner.lock_sources(root)
        started = inherited['plan']['started'] if inherited else time.time()
        plan = {'case': CASE, 'started': started, 'deadline': started + 1800,
            'workflow_target': 200000, 'batch_reported_token_allowance': 400000,
            'max_trials': 1, 'max_revisions': 1, 'prior_coding_exposure': True,
            'source_lock': sha(root / 'experiments/source-lock.json'),
            'scheduler': sha(Path(__file__)), 'historical_scores': history(),
            'parent_startup': {k: v for k, v in inherited.items() if k != 'plan'} if inherited else None,
            'limitations': 'Consumed development repeat, new identity. No blind author. '
                           'Turn-boundary usage may overshoot; no paired or causal claim.'}
        write(root / 'plan.json', plan)
        write(root / 'plan.lock.json', {'sha256': sha(root / 'plan.json')})
        write(root / 'controller.json', {'pid': os.getpid(), 'started': started})

        def guard():
            if time.time() >= plan['deadline']:
                raise RuntimeError('Lean trial deadline expired')
            if sha(root / 'plan.json') != json.loads((root / 'plan.lock.json').read_text())['sha256']:
                raise RuntimeError('Lean trial plan changed')
            if sha(Path(__file__)) != plan['scheduler']:
                raise RuntimeError('Lean trial scheduler changed')
            runner.lock_sources(root)
            quota = account_usage(runner.BINARY, runner.AUTH)
            write(root / 'quota.json', quota)
            if not can_start(quota):
                raise RuntimeError('Ordinary quota admission blocked; no model call')

        class GuardedLean(LeanEngine):
            def _worker(self, run_id, *args, **kwargs):
                guard()
                if self.store.get(run_id)['observed_tokens'] >= plan['batch_reported_token_allowance']:
                    raise RuntimeError('Lean trial token allowance exhausted')
                return super()._worker(run_id, *args, **kwargs)

        try:
            guard()
            score = runner.run_case(root, CASE, 'lean', start_guard=guard, engine_factory=GuardedLean)
            for name, expected in plan['historical_scores'].items():
                if sha(Path(name)) != expected:
                    raise RuntimeError('Historical score changed: ' + name)
            runner.lock_sources(root)
            write(root / 'audit.json', {'complete': True, 'score': score,
                'score_sha256': sha(root / 'experiments/heldout-results' / ('lean-' + CASE + '-1') / 'score.json'),
                'prior_coding_exposure': True, 'historical_scores_verified': len(plan['historical_scores']),
                'limitations': plan['limitations'],
                'token_allowance_exceeded': score['observed_tokens'] > plan['batch_reported_token_allowance']})
        except Exception as error:
            write(root / 'stop.json', {'error': str(error), 'time': time.time(), 'retry_allowed': False})
            raise
        finally:
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})


if __name__ == '__main__':
    import sys
    run(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
