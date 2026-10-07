"""Frozen three-arm stopping-policy pilot; no automatic harness promotion."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.grader import grade, register_vendor
from benchmarks.polybench.preflight import reference_valid
from benchmarks.polybench.storage_lifecycle import release_images
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.agent_search import metrics
from hx.code_search import seal, sha
from hx.config import canonical
from hx.models import HXError
from hx.store import atomic_write
from hx.worker_scaffold import validate_scaffold
from scripts.agent_search_polybench import PolyBenchBackend
from scripts.overnight_limits import account_usage, can_start
from scripts.run_lean_three import prior_evidence
from scripts.worker_scaffold_search import exercise_scaffold

CASES = ['sveltejs__svelte-630', 'serverless__serverless-3457', 'mui__material-ui-20232', 'sveltejs__svelte-3403']
ARMS = ['baseline', 'extra-check', 'compatibility-review']
PROPOSAL = Path('.hx/stopping-policy-pilot-proposal-v1')
SURVEY = Path('.hx/environment-twentyfive-v1')
ORIGINAL = Path('.hx/coding-seventeen-v1')


def write(path, value):
    atomic_write(path, canonical(value))


def better(review, comparator):
    pairs = {(r.case, r.repeat): r for r in comparator}
    a, b = metrics(review), metrics(comparator)
    return (all(not pairs[r.case, r.repeat].official_resolved or r.official_resolved for r in review)
            and (a['official_resolutions'] > b['official_resolutions']
                 or (a['official_resolutions'] == b['official_resolutions']
                     and a['reported_tokens'] < b['reported_tokens'])))


def run(root):
    root = root.resolve()
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise HXError('New pilot root required; never resume consumed root')
        root.mkdir()
        started = time.time()
        write(root / 'controller.json', {'pid': os.getpid(), 'started': started})
        private = Path('/opt/hx-polybench-runtime/v1') / root.name
        prepared = root / 'prepared'
        prepared.mkdir()
        _, _, history = prior_evidence()
        history.update({str(p.resolve()): sha(p.read_bytes()) for p in Path('.hx').glob('*/score.json')})
        used = {json.loads(Path(p).read_text()).get('case') for p in history}
        if used.intersection(CASES):
            raise HXError('Selected case already coded')
        for case in CASES:
            child = ORIGINAL / 'tasks' / case
            for descriptor in child.glob('experiments/*/*/state/native-state.json'):
                raise HXError('Selected task has prior native coding descriptor: ' + str(descriptor))
        selection = json.loads((ORIGINAL / 'selection.json').read_text())
        cases = [next(c for c in selection['cases'] if c['id'] == case) for case in CASES]
        shutil.copyfile(ORIGINAL / 'dataset.csv', prepared / 'dataset.csv')
        shutil.copyfile(ORIGINAL / 'storage.json', prepared / 'storage.json')
        storage = json.loads((prepared / 'storage.json').read_text())
        storage['execution_root'] = str(private)
        write(prepared / 'storage.json', storage)
        write(prepared / 'selection.json', {**selection, 'cases': cases})
        (prepared / 'settings.toml').write_text('''adapter = "codex"
workflow = "single"
worker_model = "gpt-6.1-sol"
judgment_model = "gpt-6.1-sol"
reasoning_effort = "medium"
max_attempts = 1
max_revisions = 1
repair_token_reserve = 100000
max_observed_tokens = 500000
attempt_timeout_seconds = 600
verification_timeout_seconds = 180
run_timeout_seconds = 2400
max_log_bytes = 20000000
''')
        images = {}
        for c in cases:
            source = SURVEY / 'cases' / c['id'] / 'source.json'
            pin = json.loads(source.read_text())
            if subprocess.check_output(['git', '-C', pin['repo_path'], 'rev-parse', 'HEAD'], text=True).strip() != pin['sanitized_base']:
                raise HXError('Original public source changed')
            if subprocess.check_output(['git', '-C', pin['repo_path'], 'status', '--porcelain'], text=True):
                raise HXError('Original public source dirty')
            pin['execution_root'] = str(private)
            images[c['id']] = pin
        (prepared / 'public').mkdir(exist_ok=True)
        for c in cases:
            shutil.copyfile(ORIGINAL / 'tasks' / c['id'] / 'public' / (c['id'] + '.json'), prepared / 'public' / (c['id'] + '.json'))
        write(prepared / 'images.json', images)
        write(root / 'backend-config.json', {'prepared_root': str(prepared), 'private_root': str(private),
              'case_provenance': {k: {'reference_informed': False, 'previous_coding_exposure': False} for k in CASES}})
        paths = [Path(__file__), Path('scripts/agent_search_polybench.py'), Path('scripts/overnight_limits.py'),
                 Path('scripts/run_lean_three.py'), Path('scripts/worker_scaffold_search.py'), Path('scripts/run_agent_search.py'),
                 *Path('src/hx').glob('*.py'), *Path('src/hx/prompts').glob('*.md'), *Path('src/hx/scaffolds').glob('*.py'),
                 *Path('benchmarks/polybench').glob('*.py'), *(runner.VENDOR / 'src').rglob('*.py'), runner.BINARY,
                 *[p for p in PROPOSAL.glob('*') if p.is_file()], root / 'backend-config.json', *[p for p in prepared.rglob('*') if p.is_file()]]
        plan = {'development': CASES[:2], 'heldout': CASES[2:], 'arms': ARMS, 'repeats': 2,
                'planned_development_trials': 12, 'conditional_heldout_trials': 12,
                'started': started, 'deadline': started + 28800, 'max_reported_tokens': 9000000,
                'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium', 'per_workflow_target': 500000,
                'repair_reserve': 100000, 'trial_token_headroom': 750000,
                'source_locks': {str(p.resolve()): sha(p.read_bytes()) for p in paths}, 'historical_scores': history,
                'proposal_model_calls': 0, 'selection_rule': 'First four uncoded ready cases in prior17 order; first2dev/last2reserved; no substitutions',
                'authorization': 'User ok go after recommended small controlled pilot; fixed9M/8h ceiling, not prior allowance reuse.',
                'limitation': 'Tiny readiness-selected paired pilot; repeats not statistical proof, no leaderboard/general causal claim. Declared identical per-arm ceilings can overshoot in flight. No automatic promotion.'}
        write(root / 'plan.json', plan)
        write(root / 'plan.lock.json', {'sha256': sha((root / 'plan.json').read_bytes())})
        tokens, rows, frozen = 0, {}, {}

        def control(headroom=0):
            if time.time() >= plan['deadline'] or tokens + headroom > plan['max_reported_tokens']:
                raise HXError('Pilot original allowance/deadline exhausted')
            for name, digest in {**plan['source_locks'], **history, **frozen}.items():
                if sha(Path(name).read_bytes()) != digest:
                    raise HXError('Pilot source/input/history lock changed: ' + name)
            if sha((root / 'plan.json').read_bytes()) != sha(canonical(plan)):
                raise HXError('Pilot plan changed')

        def admission(headroom=750000):
            control(headroom)
            q = account_usage(runner.BINARY, runner.AUTH)
            write(root / 'quota.json', q)
            if not can_start(q):
                raise HXError('Quota blocked; preserve partials, no automatic retry or purchases')
            if shutil.disk_usage(Path.cwd()).free < 40 * 1024**3:
                raise HXError('40 GiB storage guard blocked')

        def report(phase):
            write(root / 'results.json', {'phase': phase, 'reported_tokens': tokens,
                  'rows': {k: [r.model_dump() for r in v] for k, v in rows.items()},
                  'metrics': {k: metrics(v) for k, v in rows.items()}, 'limitation': plan['limitation']})

        try:
            register_vendor(runner.VENDOR.resolve())
            data = {r['instance_id']: r for r in runner.read_rows(prepared / 'dataset.csv')}
            _, _, client, settings = runner.resources(prepared)
            try:
                for case in CASES:
                    admission()
                    child = root / 'preparation' / case
                    child.mkdir(parents=True)
                    for name in ('dataset.csv', 'settings.toml', 'storage.json'):
                        shutil.copyfile(prepared / name, child / name)
                    write(child / 'selection.json', {**selection, 'cases': [next(c for c in cases if c['id'] == case)]})
                    write(child / 'images.json', {case: images[case]})
                    write(root / 'phase.json', {'phase': 'model_free_gates', 'case': case})
                    runner.ensure_image(client, child, images[case])
                    receipt = worker_environment_check(client, images[case], Path(images[case]['repo_path']),
                              child / 'worker-preflight', settings, control, lambda *args: None)
                    base = grade(data[case], '', child / 'private-preflight/base', client)
                    reference = grade(data[case], data[case]['patch'], child / 'private-preflight/reference', client)
                    gate = {'case': case, 'valid': reference_valid(base, reference), 'base_resolved': base['resolved'],
                            'reference_resolved': reference['resolved'], 'image_id': images[case]['image_id'],
                            'dataset_sha256': selection['dataset_sha256'], 'gate_version': 'official-resolution@2'}
                    write(prepared / 'preflight' / case / 'validation.json', gate)
                    write(child / 'worker-receipt.json', receipt)
                    write(child / 'release.json', release_images(client, [images[case]]))
                    if not gate['valid']:
                        raise HXError('Selected environment/reference gate failed; no replacement or coding')
            finally:
                client.close()
            backend = PolyBenchBackend(root / 'backend-config.json')
            for arm in ARMS:
                source = PROPOSAL / (arm + '.py')
                validate_scaffold(source.read_bytes())
                if not exercise_scaffold(source, private / ('fixture-' + arm)):
                    raise HXError('Executable policy fixture failed: ' + arm)
            frozen = {str(p.resolve()): sha(p.read_bytes()) for p in prepared.rglob('*') if p.is_file()}
            write(root / 'runtime-freeze.json', frozen)
            engine_plan = SimpleNamespace(**{**plan, 'development': CASES, 'heldout': [], 'source_locks': {**plan['source_locks'], **frozen}})
            backend.admit(engine_plan)
            selection_hash = None
            for split, selected in [('development', CASES[:2]), ('heldout', CASES[2:])]:
                if split == 'heldout':
                    review = rows['development/compatibility-review']
                    eligible = all(better(review, rows['development/' + arm]) for arm in ARMS[:2])
                    choice = {'review_eligible': eligible, 'hypotheses_frozen_before_trials': True,
                              'rule': 'No paired solve loss and higher official passes, or same passes with fewer tokens, vs both baseline and extra-check'}
                    write(root / 'selection.json', choice)
                    selection_hash = sha((root / 'selection.json').read_bytes())
                    if not eligible:
                        break
                for case in selected:
                    for repeat in (1, 2):
                        order = ARMS if repeat == 1 else list(reversed(ARMS))
                        for arm in order:
                            admission()
                            write(root / 'phase.json', {'phase': split, 'case': case, 'repeat': repeat, 'arm': arm})
                            directory = root / split / case / f'{arm}-{repeat}'
                            directory.mkdir(parents=True)
                            write(directory / 'started.json', {'time': time.time()})
                            trial = backend.evaluate(PROPOSAL / (arm + '.py'), case, repeat, directory, engine_plan, control)
                            tokens += trial.reported_tokens
                            write(directory / 'score.json', trial.model_dump())
                            rows.setdefault(split + '/' + arm, []).append(trial)
                            report(split)
                            if not trial.usage_known or trial.infrastructure_error or trial.missing_observations:
                                raise HXError('Operational/unknown usage trial; preserve and stop')
                    _, _, client, _ = runner.resources(prepared)
                    try:
                        write(root / f'release-{case}.json', release_images(client, [images[case]]))
                    finally:
                        client.close()
            control()
            if selection_hash and sha((root / 'selection.json').read_bytes()) != selection_hash:
                raise HXError('Frozen selection changed')
            write(root / 'final-audit.json', {'complete': True, 'reported_tokens': tokens,
                  'historical_scores_verified': len(history), 'heldout_executed': any(k.startswith('heldout/') for k in rows),
                  'rows': {k: [r.model_dump() for r in v] for k, v in rows.items()}, 'automatic_promotion': False,
                  'limitation': plan['limitation']})
            report('completed')
        except BaseException as error:
            write(root / 'stop.json', {'error': str(error), 'reported_tokens': tokens, 'unreturned_usage_may_be_unknown': True, 'retry_allowed': False})
            report('stopped')
            raise
        finally:
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})
            write(root / 'archive-lock.json', {'files': seal(root)})


if __name__ == '__main__':
    run(Path(sys.argv[1]))
