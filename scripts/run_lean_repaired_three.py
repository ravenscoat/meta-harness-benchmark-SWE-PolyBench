"""Three untouched pinned-dataset tasks; frozen lean engine and common scorer."""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.image_cache import VERSION as IMAGE_LIFECYCLE_VERSION
from benchmarks.polybench.lean import LeanEngine
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.worker_environment import worker_environment_check
from scripts.overnight_limits import account_usage, can_start
from scripts.run_paper_benchmark import usage

REPOS = ['mui/material-ui', 'sveltejs/svelte', 'serverless/serverless']
SEED = 'lean-fresh-three-v1'
SOURCE = Path('.hx/polybench-v1')


def prior_evidence():
    roots = list(Path('.hx').glob('*/selection.json'))
    roots += list(Path('.hx').glob('*/tasks/*/selection.json'))
    excluded = set()
    records = {}
    for path in roots:
        value = json.loads(path.read_text())
        if isinstance(value, dict):
            excluded.update(c['id'] for c in value.get('cases', []))
            records[str(path.resolve())] = sha(path)
    patterns = ['*/experiments/*/*/score.json', '*/tasks/*/experiments/*/*/score.json']
    scores = {str(p.resolve()): sha(p) for pattern in patterns for p in Path('.hx').glob(pattern)}
    for name in scores:
        value = json.loads(Path(name).read_text())
        excluded.add(value.get('case', value.get('instance_id')))
    for path in Path('.hx').glob('*/exposure.json'):
        value = json.loads(path.read_text())
        excluded.update(value.get('cases', []))
        records[str(path.resolve())] = sha(path)
    # Also exclude task identities in archived native-state descriptors, even unscored.
    for pattern in ['*/experiments/*/*/state/native-state.json',
                    '*/tasks/*/experiments/*/*/state/native-state.json']:
        for path in Path('.hx').glob(pattern):
            records[str(path.resolve())] = sha(path)
            excluded.add(path.parent.parent.name.removesuffix('-1').split('-', 1)[-1])
    return excluded, records, scores


def select_cases(rows, excluded):
    cases = []
    for repo in REPOS:
        eligible = [r for r in rows if r['repo'] == repo and r['instance_id'] not in excluded
                    and r['task_category'] in {'Bug Fix', 'Feature'}
                    and 10 <= len(r['problem_statement']) <= 11500]
        eligible.sort(key=lambda r: hashlib.sha256((SEED + r['instance_id']).encode()).hexdigest())
        if not eligible:
            raise RuntimeError('No untouched eligible task for ' + repo)
        row = eligible[0]
        cases.append({'id': row['instance_id'], 'repo': repo, 'split': 'evaluation',
                      'language': row['language'], 'category': row['task_category'],
                      'upstream_base': row['base_commit']})
    return cases


def check_headroom(tokens, now, plan, initial):
    reserve, seconds = (450000, 1500) if initial else (150000, 630)
    if tokens + reserve > plan['max_reported_tokens'] or now + seconds >= plan['deadline']:
        raise RuntimeError('Batch budget/deadline headroom exhausted')


def report(root, plan):
    rows, tokens, pending = usage(root)
    for row in rows:
        row['classification'] = ('official_resolution' if row['official_resolved'] else
            'grader_infrastructure_error' if row.get('grader_error') else
            'patch_rejected' if row.get('candidate_patch_error') else
            'no_accepted_candidate' if not row['acceptance'].get('candidate_commit') else
            'required_tests_unobserved' if row.get('unobserved_acceptance_tests') else
            'observed_required_test_failure')
    ids = [row['case'] for row in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(plan['cases']):
        raise RuntimeError('Unexpected scored identities')
    result = {'planned_trials': 3, 'complete': set(ids) == set(plan['cases']),
              'scored_trials': len(rows), 'rows': rows, 'reported_tokens': tokens,
              'unscored_runs': pending, 'official_resolutions': sum(r['official_resolved'] for r in rows),
              'workflow_seconds': sum(r['seconds'] for r in rows),
              'limitations': plan['limitations']}
    write(root / 'results.json', result)
    return result


def validate(root, plan, frozen=False):
    if sha(root / 'plan.json') != json.loads((root / 'plan.lock.json').read_text())['sha256']:
        raise RuntimeError('Plan changed')
    for name, expected in {**plan['historical_scores'], **plan['inputs'], **plan['scheduler'],
                           **plan['runtime']}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Sealed evidence changed: ' + name)
    if frozen:
        runner.lock_sources(root)



def verify_parent(parent, repair):
    plan = json.loads((parent / 'plan.json').read_text())
    seal = json.loads((repair / 'final-validation.json').read_text())
    if not seal['complete'] or not seal['all_three_real_worker_preflights_passed']:
        raise RuntimeError('Repair validation incomplete')
    if sha(repair / 'audit.json') != seal['audit_sha256'] or sha(repair / 'repair-source-lock.json') != seal['source_lock_sha256']:
        raise RuntimeError('Repair evidence changed')
    required = {'plan.json': seal['old_batch_plan_sha256'], 'stop.json': seal['old_batch_stop_sha256']}
    for name, expected in required.items():
        if sha(parent / name) != expected:
            raise RuntimeError('Parent evidence changed')
    if sha(parent / 'plan.json') != json.loads((parent / 'plan.lock.json').read_text())['sha256']:
        raise RuntimeError('Parent plan changed')
    if not (parent / 'controller.exited.json').exists():
        raise RuntimeError('Parent has not exited')
    reject_consumed_parent(parent)
    for name, expected in json.loads((repair / 'repair-source-lock.json').read_text()).items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Validated repair source changed')
    for name, expected in plan['historical_scores'].items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Historical score changed')
    for case in plan['cases']:
        if not json.loads((parent / 'preflight' / case / 'validation.json').read_text())['valid']:
            raise RuntimeError('Parent reference gate invalid')
    check_headroom(0, time.time(), plan, True)
    return plan


def reject_consumed_parent(parent):
    for pattern in ['experiments/*/*/score.json', 'experiments/*/*/state/native-state.json']:
        if next(parent.glob(pattern), None) is not None:
            raise RuntimeError('Parent coding identity already consumed')

def run(root):
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise RuntimeError('New root required; never retry consumed identities')
        os.environ['PATH'] = str(runner.BINARY.parent) + os.pathsep + os.environ.get('PATH', '')
        parent = Path('.hx/lean-reliability-three-v2')
        repair = Path('.hx/image-lifecycle-repair-v2')
        original_plan = verify_parent(parent, repair)
        historical = original_plan['historical_scores']
        cases = json.loads((parent / 'selection.json').read_text())['cases']
        root.mkdir(parents=True)
        for name in ['dataset.csv', 'storage.json', 'selection.json', 'settings.toml', 'images.json']:
            shutil.copyfile(parent / name, root / name)
        for case in cases:
            name = case['id']
            write(root / 'public' / (name + '.json'), json.loads((parent / 'public' / (name + '.json')).read_text()))
            write(root / 'preflight' / name / 'validation.json', json.loads((parent / 'preflight' / name / 'validation.json').read_text()))
        (root / 'experiments').mkdir()
        write(root / 'image-retention.json', {'version': IMAGE_LIFECYCLE_VERSION, 'cases': original_plan['cases']})
        names = ['dataset.csv', 'selection.json', 'storage.json', 'settings.toml', 'images.json', 'image-retention.json']
        names += ['public/' + c['id'] + '.json' for c in cases]
        names += ['preflight/' + c['id'] + '/validation.json' for c in cases]
        provenance = [parent / 'plan.json', parent / 'plan.lock.json', parent / 'stop.json', parent / 'controller.exited.json',
                      repair / 'final-validation.json', repair / 'audit.json', repair / 'repair-source-lock.json']
        started = original_plan['started']
        plan = {**original_plan,
                'parent': str(parent.resolve()), 'created': time.time(),
                'inputs': {str(p.resolve()): sha(p) for p in [*[root / n for n in names], *provenance]},
                'scheduler': {str(p.resolve()): sha(p) for p in [Path(__file__), Path('scripts/run_lean_three.py'),
                    Path('scripts/overnight_limits.py'), Path('scripts/run_paper_benchmark.py')]},
                'runtime': {str(p.resolve()): sha(p) for p in [*Path('benchmarks/polybench').glob('*.py'),
                    *Path('src/hx').glob('*.py'), *Path('src/hx/prompts').glob('*.md')]},
                'limitations': 'Same three previously selected, model-free-prepared tasks. Parent had no coding identities. Original deadline and token allowance inherited. New repaired runtime; no blind author or paired/causal/leaderboard claim. Turn-boundary caps can overshoot.'}
        write(root / 'plan.json', plan)
        write(root / 'plan.lock.json', {'sha256': sha(root / 'plan.json')})
        write(root / 'controller.json', {'pid': os.getpid(), 'started': time.time(), 'envelope_started': started})
        frozen = False

        def admission(initial=False):
            result = report(root, plan)
            check_headroom(result['reported_tokens'], time.time(), plan, initial)
            validate(root, plan, frozen)
            quota = account_usage(runner.BINARY, runner.AUTH)
            write(root / 'quota.json', quota)
            if not can_start(quota):
                raise RuntimeError('Quota admission blocked; no purchases or reset credits')

        try:
            admission(initial=True)
            write(root / 'phase.json', {'phase': 'all_task_environment_preflight', 'updated': time.time()})
            gates = [json.loads((root / 'preflight' / c['id'] / 'validation.json').read_text()) for c in cases]
            write(root / 'preflight.json', {'gates': gates, 'all_three_passed': all(g['valid'] for g in gates)})
            if not all(g['valid'] for g in gates):
                raise RuntimeError('Environment gate blocked; no substituted case or model work')
            _, images, client, settings = runner.resources(root)
            try:
                receipts = []
                for case in cases:
                    admission(initial=True)
                    runner.ensure_image(client, root, images[case['id']])
                    receipts.append(worker_environment_check(client, images[case['id']],
                        Path(images[case['id']]['repo_path']), root / 'worker-preflight' / case['id'],
                        settings, lambda: check_headroom(report(root, plan)['reported_tokens'],
                            time.time(), plan, True), lambda *args: None))
                write(root / 'worker-preflight.json', {'all_three_passed': True, 'receipts': receipts})
            finally:
                client.close()
            runner.lock_sources(root)
            frozen = True
            write(root / 'runtime-freeze.json', {'source_lock_sha256': sha(root / 'experiments/source-lock.json'),
                  'time': time.time(), 'model_calls_before_freeze': 0})
            class GuardedLean(LeanEngine):
                def _worker(self, *args, **kwargs):
                    admission()
                    return super()._worker(*args, **kwargs)
            for case in cases:
                admission(initial=True)
                write(root / 'phase.json', {'phase': 'coding', 'case': case['id'], 'updated': time.time()})
                runner.run_case(root, case['id'], 'lean', start_guard=lambda: admission(True), engine_factory=GuardedLean)
                result = report(root, plan)
                print(json.dumps({'event': 'lean_batch_scored', 'scored': result['scored_trials'],
                                  'official_resolutions': result['official_resolutions']}), flush=True)
                if result['unscored_runs'] or any(r.get('usage_known') is False or r.get('grader_error') for r in result['rows']):
                    raise RuntimeError('Operational or unknown-usage blocker retained')
            validate(root, plan, True)
            write(root / 'audit.json', {'complete': report(root, plan)['complete'],
                  'historical_scores_verified': len(historical),
                  'score_sha256': {str(p.relative_to(root)): sha(p) for p in root.glob('experiments/heldout-results/*/score.json')}})
        except BaseException as error:
            write(root / 'stop.json', {'error': str(error), 'type': type(error).__name__,
                  'time': time.time(), 'retry_allowed': False})
            raise
        finally:
            report(root, plan)
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})


if __name__ == '__main__':
    import sys
    run(Path(sys.argv[1]))
