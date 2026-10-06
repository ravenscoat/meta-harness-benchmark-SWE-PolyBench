"""Three real task outcomes, isolated and preflighted before any coding work."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.containers import command, create, populate
from benchmarks.polybench.image_cache import ensure_image
from benchmarks.polybench.independent import VERSION, IndependentEngine
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.worker_environment import build_check
from scripts.overnight_limits import account_usage, can_start
from scripts.run_fresh_remaining_benchmark import history
from scripts.run_paper_benchmark import usage
from scripts.worker_scaffold_search import select_for_experiment

CASES = ['mui__material-ui-22696', 'mui__material-ui-36353', 'mui__material-ui-34207']
SOURCE = Path('.hx/polybench-v1')


def prepare(root, not_before):
    if root.exists():
        raise RuntimeError('New batch root required')
    original = json.loads((SOURCE/'selection.json').read_text())
    images = json.loads((SOURCE/'images.json').read_text())
    historical = history()
    root.mkdir(parents=True)
    inputs = {}
    for key in CASES:
        child = root/'tasks'/key
        select_for_experiment(child, Path('.hx/worker-loop-runtime-v14'))
        cases = [c for c in original['cases'] if c['id'] == key and c['split'] == 'evaluation']
        if len(cases) != 1:
            raise RuntimeError('Expected exact original metadata')
        for name in ['dataset.csv', 'storage.json']:
            shutil.copyfile(SOURCE/name, child/name)
        shutil.copyfile('.hx/remaining-quota-benchmark-v1/settings.toml', child/'settings.toml')
        write(child/'selection.json', {**original, 'cases': cases})
        write(child/'images.json', {key: images[key]})
        for directory, name in [('public', key+'.json'), ('preflight/'+key, 'validation.json')]:
            (child/directory).mkdir(parents=True)
            shutil.copyfile(SOURCE/directory/name, child/directory/name)
        gate = json.loads((child/'preflight'/key/'validation.json').read_text())
        if not gate['valid'] or gate['image_id'] != images[key]['image_id']:
            raise RuntimeError('Invalid pinned environment')
        (child/'experiments').mkdir()
        runner.lock_sources(child)
        for name in ['selection.json', 'images.json', 'settings.toml', 'dataset.csv', 'storage.json',
                     'worker-scaffold.py', 'worker-scaffold.lock.json', 'public/'+key+'.json',
                     'preflight/'+key+'/validation.json']:
            inputs[str((child/name).resolve())] = sha(child/name)
    now = time.time()
    not_before = max(now, not_before)
    if not_before > now+18000:
        raise RuntimeError('Expected bounded natural quota reset')
    exposure = {key: any(json.loads(Path(p).read_text()).get('case',
        json.loads(Path(p).read_text()).get('instance_id')) == key for p in historical) for key in CASES}
    plan = {'cases': CASES, 'started': now, 'not_before': not_before,
        'deadline': not_before+14400, 'max_reported_tokens': 3600000, 'parallelism': 1,
        'planned_trials': 3, 'model': 'gpt-6.1-sol', 'max_revisions': 1, 'protocol': VERSION,
        'per_workflow_target': 900000, 'quota_limits': {'primary_exclusive': 80, 'weekly_exclusive': 90},
        'prior_coding_exposure': exposure, 'inputs': inputs, 'historical_scores': historical,
        'scheduler': {str(p.resolve()): sha(p) for p in [Path(__file__),
            Path('scripts/overnight_limits.py'), Path('scripts/run_paper_benchmark.py'),
            Path('scripts/run_fresh_remaining_benchmark.py'),
            Path('.hx/worker-loop-runtime-v14/archive-lock.json')]},
        'authorization': 'User requested genuine batch execution and diagnosis of batch infrastructure. One fresh task and two separately identified consumed development repeats; old scores never replaced.',
        'limitations': 'Sequential batch, not concurrent model work. Two consumed cases, no fresh three-task accuracy or paired/causal/leaderboard claim. Turn-boundary budgets can overshoot. No private grader/solution context or purchases/reset credits.'}
    write(root/'plan.json', plan)
    write(root/'plan.lock.json', {'sha256': sha(root/'plan.json')})


def validate(root, plan):
    if sha(root/'plan.json') != json.loads((root/'plan.lock.json').read_text())['sha256']:
        raise RuntimeError('Batch plan changed')
    for name, expected in {**plan['historical_scores'], **plan['scheduler'], **plan['inputs']}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Sealed evidence changed: '+name)
    for key in CASES:
        runner.lock_sources(root/'tasks'/key)


def report(root, plan):
    rows, tokens, interrupted = [], 0, []
    for key in CASES:
        scored, used, pending = usage(root/'tasks'/key)
        rows.extend(scored)
        tokens += used
        interrupted.extend(pending)
    unique = {row['case'] for row in rows}
    if len(rows) != len(unique) or not unique.issubset(CASES):
        raise RuntimeError('Unexpected or duplicate scored identity')
    for row in rows:
        row['prior_coding_exposure'] = plan['prior_coding_exposure'][row['case']]
    result = {'planned_trials': 3, 'scored_trials': len(rows), 'complete': unique == set(CASES),
        'official_resolutions': sum(bool(r['official_resolved']) for r in rows),
        'workflow_successes': sum(bool(r['task_success']) for r in rows), 'rows': rows,
        'reported_tokens': tokens, 'interrupted_unscored_runs': interrupted,
        'remaining_cases': [key for key in CASES if key not in unique],
        'limitations': plan['limitations']}
    write(root/'results.json', result)
    return result


def admission(root, plan, step=None):
    result = report(root, plan)
    if result['interrupted_unscored_runs'] and step is None:
        raise RuntimeError('Interrupted coding identity retained; no silent retry')
    if any(row.get('usage_known') is False for row in result['rows']):
        raise RuntimeError('Unknown usage; further model calls blocked')
    reserve, seconds = (1050000, 2430) if step is None else (150000, 630)
    if result['reported_tokens']+reserve > plan['max_reported_tokens'] or time.time()+seconds >= plan['deadline']:
        raise RuntimeError('Batch token/time headroom exhausted')
    quota = account_usage(runner.BINARY, runner.AUTH)
    write(root/'quota.json', quota)
    if not can_start(quota):
        raise RuntimeError('Quota blocks model work; no credits used')
    validate(root, plan)


def preflight(root, key):
    child = root/'tasks'/key
    directory = child/'batch-preflight'
    if (directory/'receipt.json').exists():
        raise RuntimeError('Preflight identity already recorded; inspect evidence')
    _, images, client, settings = runner.resources(child)
    case = images[key]
    container = None
    try:
        ensure_image(client, child, case)
        container, workdir = create(client, case, offline=True)
        populate(container, workdir, Path(case['repo_path']), case)
        start = time.monotonic()
        def control():
            if time.monotonic()-start > 600:
                raise RuntimeError('Preflight deadline')
        build = build_check(container, workdir, Path(case['repo_path']), case,
                            directory/'build', settings, control, lambda *args: None)
        if build and not build.passed:
            raise RuntimeError('Public source build failed before batch coding')
        probe = "const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json'));if(!p.scripts||!Object.keys(p.scripts).some(k=>k==='test'||k.startsWith('test:')))throw Error('No public test script');require.resolve('mocha');fs.writeFileSync('.hx-batch-smoke','ok');fs.unlinkSync('.hx-batch-smoke');console.log(JSON.stringify({node:process.version,public_test_manifest:true,mocha_available:true,workspace_writable:true}));"
        smoke = json.loads(command(container, ['node', '-e', probe], workdir, '1000:1000'))
        status = command(container, ['git', 'status', '--porcelain'], workdir, '1000:1000')
        if status.strip():
            raise RuntimeError('Preflight mutated tracked repository')
        receipt = {'case': key, 'passed': True, 'image_id': case['image_id'],
            'container_id': container.id, 'worker_uid': 1000, 'offline': True,
            'model_calls': 0, 'official_calls': 0, 'source_clean': True, 'smoke': smoke,
            'build_passed': build.passed if build else None,
            'limitation': 'Preparation smoke test only; public behavioral and official tests run per coding task.'}
        write(directory/'receipt.json', receipt)
        return receipt
    finally:
        if container:
            container.remove(force=True)
        client.close()


def run(root):
    plan = json.loads((root/'plan.json').read_text())
    if plan['cases'] != CASES:
        raise RuntimeError('Unexpected fixed case set')
    original = runner.PolyEngine
    with FileLock('.hx/single-evaluation-controller.lock').acquire(timeout=0):
        validate(root, plan)
        if any((root/'tasks'/key/'controller.json').exists() for key in CASES):
            raise RuntimeError('Child identities already launched; no implicit rerun')
        write(root/'controller.json', {'pid': os.getpid(), 'started': time.time()})
        try:
            while True:
                if time.time()+2430 >= plan['deadline']:
                    raise RuntimeError('Quota wait exhausted batch deadline')
                quota = account_usage(runner.BINARY, runner.AUTH)
                write(root/'quota.json', quota)
                if time.time() >= plan['not_before'] and can_start(quota):
                    break
                write(root/'phase.json', {'phase': 'waiting_for_quota', 'updated': time.time()})
                time.sleep(60)
            validate(root, plan)
            receipts = []
            for key in CASES:
                write(root/'phase.json', {'phase': 'preflighting_all_tasks', 'case': key, 'updated': time.time()})
                receipts.append(preflight(root, key))
            if len({r['container_id'] for r in receipts}) != 3:
                raise RuntimeError('Task container isolation failed')
            write(root/'preflight.json', {'all_three_passed': True, 'receipts': receipts})
            for key in CASES:
                admission(root, plan)
                child = root/'tasks'/key
                class Guarded(IndependentEngine):
                    def _worker(self, *args, **kwargs):
                        admission(root, plan, args[1])
                        reserve = 350000 if args[1] == 'implement' else self.settings.repair_token_reserve
                        if self.model_headroom(args[0]) < reserve:
                            raise RuntimeError('Implementation/repair reserve unavailable')
                        return super()._worker(*args, **kwargs)
                runner.PolyEngine = Guarded
                write(root/'phase.json', {'phase': 'coding', 'case': key, 'updated': time.time()})
                write(child/'controller.json', {'pid': os.getpid(), 'started': time.time(), 'case': key})
                try:
                    runner.run_case(child, key, 'full', start_guard=lambda: admission(root, plan, 'before-worker'))
                finally:
                    write(child/'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})
                result = report(root, plan)
                print(json.dumps({'event': 'batch_task_scored', 'case': key,
                      'scored_trials': result['scored_trials'], 'official_resolutions': result['official_resolutions']}), flush=True)
                if result['rows'][-1].get('grader_error') or result['interrupted_unscored_runs']:
                    raise RuntimeError('Operational failure retained; inspect before further tasks')
            validate(root, plan)
            write(root/'audit.json', {'complete': report(root, plan)['complete'],
                'historical_scores_unchanged': len(plan['historical_scores']),
                'score_hashes': {str(p.relative_to(root)): sha(p) for p in root.glob('tasks/*/experiments/heldout-results/*/score.json')}})
        except BaseException as error:
            write(root/'stop.json', {'type': type(error).__name__, 'error': str(error), 'time': time.time()})
            raise
        finally:
            report(root, plan)
            write(root/'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})
            runner.PolyEngine = original


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--not-before', type=float, default=0)
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:'+os.environ['PATH']
    root = args.root.resolve()
    if args.prepare:
        prepare(root, args.not_before)
    run(root)
