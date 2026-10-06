"""One repaired Svelte development identity; waits for ordinary natural quota admission."""
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.lean import LeanEngine
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.worker_environment import worker_environment_check
from scripts.overnight_limits import account_usage, can_start

CASE = 'sveltejs__svelte-7422'

def history():
    return {str(p.resolve()): sha(p) for pattern in ['*/experiments/*/*/score.json', '*/tasks/*/experiments/*/*/score.json'] for p in Path('.hx').glob(pattern)}

def remaining(deadline, now):
    if deadline - now < 1500:
        raise RuntimeError('Insufficient deadline headroom; no new model call')


def wait_admission(deadline, inspect, validate, record, clock=time.time, sleep=time.sleep):
    """No coding identity is created while quota is unavailable."""
    while True:
        validate()
        remaining(deadline, clock())
        quota = inspect()
        record(quota)
        if can_start(quota):
            return
        sleep(60)



def run(root):
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if not runner.BINARY.is_file():
            raise RuntimeError('Pinned Codex executable missing')
        os.environ['PATH'] = str(runner.BINARY.parent) + os.pathsep + os.environ.get('PATH', '')
        if root.exists():
            raise RuntimeError('New lean development root required; never retry an existing identity')
        root.mkdir(parents=True)
        original = Path('.hx/lean-fresh-three-v1')
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
        gate = json.loads((root / 'preflight' / CASE / 'validation.json').read_text())
        if not gate['valid']:
            raise RuntimeError('Original pinned reference gate invalid; no coding')
        (root / 'settings.toml').write_text('''adapter = "codex"
workflow = "single"
worker_model = "gpt-6.1-sol"
judgment_model = "gpt-6.1-sol"
reasoning_effort = "medium"
max_attempts = 1
max_revisions = 1
repair_token_reserve = 60000
max_observed_tokens = 300000
attempt_timeout_seconds = 600
verification_timeout_seconds = 180
run_timeout_seconds = 1200
max_log_bytes = 20000000
''')
        (root / 'experiments').mkdir()
        runner.lock_sources(root)
        started = time.time()
        plan = {'case': CASE, 'started': started, 'deadline': started + 10800,
            'workflow_target': 300000, 'batch_reported_token_allowance': 600000,
            'max_trials': 1, 'max_revisions': 1, 'prior_coding_exposure': True,
            'source_lock': sha(root / 'experiments/source-lock.json'),
            'scheduler': sha(Path(__file__)), 'historical_scores': history(),
            'admission_dependency': sha(Path('scripts/overnight_limits.py')),
            'prior_setup_failure': sha(original / 'experiments/heldout-results/lean-sveltejs__svelte-7422-1/score.json'),
            'inputs': {str(p.resolve()): sha(p) for p in [root / 'selection.json', root / 'images.json', root / 'settings.toml', root / 'dataset.csv', root / 'storage.json', root / 'public' / (CASE + '.json'), root / 'preflight' / CASE / 'validation.json']},
            'limitations': 'Consumed development repeat, new identity. No blind author. '
                           'Turn-boundary usage may overshoot; no paired or causal claim.'}
        write(root / 'plan.json', plan)
        write(root / 'plan.lock.json', {'sha256': sha(root / 'plan.json')})
        write(root / 'controller.json', {'pid': os.getpid(), 'started': started})

        shutil.copyfile(__file__, root / 'scheduler-source.py')
        shutil.copyfile('scripts/overnight_limits.py', root / 'admission-source.py')

        def integrity():
            if sha(root / 'plan.json') != json.loads((root / 'plan.lock.json').read_text())['sha256']:
                raise RuntimeError('Lean trial plan changed')
            if sha(Path(__file__)) != plan['scheduler']:
                raise RuntimeError('Lean trial scheduler changed')
            if sha(root / 'experiments/source-lock.json') != plan['source_lock']:
                raise RuntimeError('Source lock changed')
            if sha(Path('scripts/overnight_limits.py')) != plan['admission_dependency']:
                raise RuntimeError('Admission dependency changed')
            for name, expected in plan['inputs'].items():
                if sha(Path(name)) != expected:
                    raise RuntimeError('Pinned input changed: ' + name)
            runner.lock_sources(root)

        def guard():
            integrity()
            remaining(plan['deadline'], time.time())
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
            def record_quota(quota):
                write(root / 'quota.json', quota)
                if not can_start(quota):
                    write(root / 'phase.json', {'phase': 'waiting_for_natural_quota_reset', 'updated': time.time(), 'model_calls': 0})
            wait_admission(plan['deadline'], lambda: account_usage(runner.BINARY, runner.AUTH),
                           integrity, record_quota)
            guard()
            _, images, client, settings = runner.resources(root)
            try:
                runner.ensure_image(client, root, images[CASE])
                receipt = worker_environment_check(client, images[CASE], Path(images[CASE]['repo_path']), root / 'worker-preflight', settings, lambda: remaining(plan['deadline'], time.time()), lambda *args: None)
                write(root / 'worker-preflight.json', receipt)
            finally:
                client.close()
            guard()
            write(root / 'phase.json', {'phase': 'coding', 'updated': time.time()})
            score = runner.run_case(root, CASE, 'lean', start_guard=guard, engine_factory=GuardedLean)
            for name, expected in plan['historical_scores'].items():
                if sha(Path(name)) != expected:
                    raise RuntimeError('Historical score changed: ' + name)
            integrity()
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
    run(Path(sys.argv[1]))
