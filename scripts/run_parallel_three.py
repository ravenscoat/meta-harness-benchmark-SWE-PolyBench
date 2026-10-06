"""Three isolated benchmark processes under one locked quota/token envelope."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.image_cache import ensure_image
from benchmarks.polybench.independent import IndependentEngine
from benchmarks.polybench.prepare import sha, write
from scripts.overnight_limits import account_usage
from scripts.run_one_react_benchmark import history
from scripts.run_paper_benchmark import usage
from scripts.worker_scaffold_search import select_for_experiment

CASES = ['sveltejs__svelte-477', 'mui__material-ui-36353', 'mui__material-ui-34207']
SOURCE = Path('.hx/polybench-v1')


def quota_allowed(quota):
    return (quota['ordinary_allowed'] and quota['primary']['usedPercent'] < 80
            and quota['secondary']['usedPercent'] < 98)


def totals(root):
    rows, tokens, incomplete = [], 0, []
    for key in CASES:
        child = root / 'tasks' / key
        if child.exists():
            scored, observed, pending = usage(child)
            rows.extend(scored)
            tokens += observed
            incomplete.extend(pending)
    return rows, tokens, incomplete


def validate(root, plan):
    if sha(root / 'plan.json') != json.loads((root / 'plan.lock.json').read_text())['sha256']:
        raise RuntimeError('Parallel plan changed')
    for name, expected in {**plan['historical_scores'], **plan['scheduler'], **plan['inputs']}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Sealed evidence changed: ' + name)
    for key in CASES:
        runner.lock_sources(root / 'tasks' / key)


def prepare(root):
    if root.exists():
        raise RuntimeError('A new parallel experiment root is required')
    historical = history()
    used = {json.loads(Path(p).read_text()).get('case') for p in historical}
    for state in Path('.hx').glob('*/experiments/*/*/state'):
        snapshots = sorted(state.glob('console-snapshot.*.json'))
        if snapshots:
            for entry in json.loads(snapshots[-1].read_text()):
                used.add(entry.get('run', {}).get('task', {}).get('id'))
    if used.intersection(CASES):
        raise RuntimeError('Selected case has prior coding exposure; no replacement')
    selection = json.loads((SOURCE / 'selection.json').read_text())
    images = json.loads((SOURCE / 'images.json').read_text())
    root.mkdir(parents=True)
    inputs = {}
    for key in CASES:
        child = root / 'tasks' / key
        select_for_experiment(child, Path('.hx/worker-loop-runtime-v9'))
        for name in ['dataset.csv', 'storage.json']:
            shutil.copyfile(SOURCE / name, child / name)
        shutil.copyfile('.hx/remaining-quota-benchmark-v1/settings.toml', child / 'settings.toml')
        metadata = [c for c in selection['cases'] if c['id'] == key]
        if len(metadata) != 1 or metadata[0]['split'] != 'evaluation':
            raise RuntimeError('Expected exact original evaluation metadata')
        write(child / 'selection.json', {**selection, 'cases': metadata})
        # Each cache may trim ONLY its own recorded image. Never share a ledger.
        write(child / 'images.json', {key: images[key]})
        for directory, name in [('public', key + '.json'), ('preflight/' + key, 'validation.json')]:
            (child / directory).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / directory / name, child / directory / name)
        gate = json.loads((child / 'preflight' / key / 'validation.json').read_text())
        if not gate['valid'] or gate['image_id'] != images[key]['image_id']:
            raise RuntimeError('Pinned environment validation invalid')
        (child / 'experiments').mkdir()
        runner.lock_sources(child)
        for name in ['selection.json', 'images.json', 'settings.toml', 'dataset.csv',
                     'storage.json', 'worker-scaffold.py', 'worker-scaffold.lock.json']:
            inputs[str((child / name).resolve())] = sha(child / name)
    now = time.time()
    plan = {'cases': CASES, 'started': now, 'deadline': now + 14400,
            'parallelism': 3, 'max_reported_tokens': 3600000,
            'per_workflow_target': 900000, 'model': 'gpt-6.1-sol', 'max_revisions': 1,
            'quota_limits': {'primary_exclusive': 80, 'weekly_exclusive': 98},
            'selection_rule': 'First three original evaluation cases with no scored or snapshot coding identity in metadata order. No outcome ranking.',
            'authorization': 'User explicitly requested three questions at the same time using the remaining allowance; no purchases or resets.',
            'historical_scores': historical, 'inputs': inputs,
            'scheduler': {str(p.resolve()): sha(p) for p in [Path(__file__),
                Path('scripts/overnight_limits.py'), Path('scripts/run_paper_benchmark.py')]},
            'limitations': 'Small selected sample, no paired baseline or causal/leaderboard claim. '
                           'Turn-boundary caps can overshoot; concurrent requests consume shared quota.'}
    write(root / 'plan.json', plan)
    write(root / 'plan.lock.json', {'sha256': sha(root / 'plan.json')})


def report(root, plan):
    rows, tokens, incomplete = totals(root)
    value = {'planned': 3, 'scored': len(rows), 'complete': len(rows) == 3,
             'official_resolved': sum(bool(r['official_resolved']) for r in rows),
             'workflow_success': sum(bool(r['task_success']) for r in rows),
             'rows': rows, 'reported_tokens': tokens, 'unscored_runs': incomplete,
             'wall_seconds': time.time() - plan['started'], 'limitations': plan['limitations']}
    write(root / 'results.json', value)
    return value


def guard(root, key, step):
    # Admission is serialized, model executions remain concurrent. No child
    # overwrites another child's quota snapshot or reservations.
    with FileLock(str(root / 'admission.lock'), timeout=180):
        plan = json.loads((root / 'plan.json').read_text())
        if time.time() + 630 >= plan['deadline']:
            raise RuntimeError('Parallel envelope deadline reached')
        rows, tokens, _ = totals(root)
        if any(r.get('usage_known') is False for r in rows):
            raise RuntimeError('Unknown usage in a scored task')
        quota = account_usage(runner.BINARY, runner.AUTH)
        write(root / ('quota-' + key + '.json'), quota)
        if not quota_allowed(quota):
            raise RuntimeError('Shared account quota stops further model calls')
        pending = json.loads((root / 'reservations.json').read_text()) if (root / 'reservations.json').exists() else {}
        reserve = 350000 if step == 'implement' else 150000
        if tokens + reserve + sum(v for k, v in pending.items() if k != key) > plan['max_reported_tokens']:
            raise RuntimeError('Shared token headroom exhausted')
        pending[key] = reserve
        write(root / 'reservations.json', pending)


def child_run(root, key):
    if key not in CASES:
        raise RuntimeError('Unknown parallel task')
    child = root / 'tasks' / key
    plan = json.loads((root / 'plan.json').read_text())
    validate(root, plan)
    rows, _, incomplete = usage(child)
    if rows or incomplete:
        raise RuntimeError('Consumed or interrupted identity cannot be rerun')
    class Guarded(IndependentEngine):
        def _worker(self, *args, **kwargs):
            guard(root, key, args[1])
            try:
                return super()._worker(*args, **kwargs)
            finally:
                with FileLock(str(root / 'admission.lock'), timeout=180):
                    reservations = json.loads((root / 'reservations.json').read_text())
                    reservations.pop(key, None)
                    write(root / 'reservations.json', reservations)
    runner.PolyEngine = Guarded
    write(child / 'controller.json', {'pid': os.getpid(), 'started': time.time(), 'case': key})
    try:
        runner.run_case(child, key, 'full', start_guard=lambda: guard(root, key, 'before-worker'))
    except BaseException as error:
        write(child / 'stop.json', {'error': str(error), 'type': type(error).__name__, 'time': time.time()})
        raise
    finally:
        write(child / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})


def run(root):
    plan = json.loads((root / 'plan.json').read_text())
    validate(root, plan)
    if (root / 'launches.json').exists():
        raise RuntimeError('Parallel launch identities already consumed; no implicit resume')
    children, handles = [], []
    write(root / 'controller.json', {'pid': os.getpid(), 'started': time.time()})
    try:
        # Finish model-free image preparation before launching all three.
        for key in CASES:
            child = root / 'tasks' / key
            _, images, client, _ = runner.resources(child)
            try:
                ensure_image(client, child, images[key])
            finally:
                client.close()
        validate(root, plan)
        if time.time() + 2430 >= plan['deadline']:
            raise RuntimeError('Image preparation left insufficient workflow time')
        guard(root, CASES[0], 'batch-start')
        write(root / 'reservations.json', {})
        for key in CASES:
            child = root / 'tasks' / key
            out = (child / 'controller.stdout.txt').open('wb')
            err = (child / 'controller.stderr.txt').open('wb')
            handles.extend([out, err])
            process = subprocess.Popen([sys.executable, '-m', 'scripts.run_parallel_three',
                str(root), '--child', key], stdout=out, stderr=err)
            children.append((key, process))
            write(root / 'launches.json', [{'case': k, 'pid': p.pid} for k, p in children])
        while any(p.poll() is None for _, p in children):
            report(root, plan)
            time.sleep(10)
        validate(root, plan)
        value = report(root, plan)
        write(root / 'audit.json', {'complete': value['complete'],
            'historical_scores_unchanged': len(plan['historical_scores']),
            'exit_codes': {key: p.returncode for key, p in children},
            'score_hashes': {str(p.relative_to(root)): sha(p) for p in root.glob('tasks/*/experiments/heldout-results/*/score.json')}})
    except BaseException as error:
        write(root / 'stop.json', {'error': str(error), 'type': type(error).__name__, 'time': time.time()})
        raise
    finally:
        for handle in handles:
            handle.close()
        report(root, plan)
        write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--child', choices=CASES)
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    root = args.root.resolve()
    if args.child:
        child_run(root, args.child)
    else:
        with FileLock('.hx/single-evaluation-controller.lock').acquire(timeout=0):
            if args.prepare:
                prepare(root)
            run(root)


if __name__ == '__main__':
    main()
