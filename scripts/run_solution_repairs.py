"""Bounded consumed-development repairs seeded from the nine saved candidates."""
import json
import os
import shutil
import time
from functools import partial
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.grader import register_vendor
from benchmarks.polybench.image_cache import VERSION, ensure_image
from benchmarks.polybench.lean import LeanEngine
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.storage_lifecycle import release_images
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.config import digest, load_settings
from hx.git import validate_candidate
from hx.models import Candidate
from scripts.overnight_limits import account_usage, can_start
from scripts.run_coding_seventeen import child_report, classify, validate
from scripts.run_lean_three import prior_evidence
from scripts.run_paper_benchmark import usage

PARENT = Path('.hx/coding-seventeen-v1')


class SeededRepair(LeanEngine):
    """Seed provenance changes identity; original task base stays authoritative."""
    def __init__(self, *args, seeds, contexts, admission, **kwargs):
        super().__init__(*args, **kwargs)
        self.seed = Candidate.model_validate(seeds[self.case['id']])
        self.seed_context = contexts[self.case['id']]
        self.admission = admission
        self.config['saved_solution_repair'] = {
            'version': 'seeded-public-repair@1',
            'seed': self.seed.model_dump(), 'public_context': self.seed_context,
        }
        self.config['fingerprint'] = digest({k: v for k, v in self.config.items() if k != 'fingerprint'})

    def _implementation(self, run_id, step_id, task, previous, feedback, deadline):
        if previous is None:
            if self.seed.base_commit != task.base_commit:
                raise RuntimeError('Saved candidate belongs to a different original base')
            validate_candidate(self.seed, task)
            previous = self.seed
            feedback = {**self.seed_context, **feedback}
        return super()._implementation(run_id, step_id, task, previous, feedback, deadline)

    def _worker(self, *args, **kwargs):
        self.admission()
        return super()._worker(*args, **kwargs)


def repair_cases(audit):
    failed = [r['score']['case'] for r in audit['records'] if not r['score']['official_resolved']]
    if len(failed) != 9 or len(set(failed)) != 9 or 'mui__material-ui-13534' not in failed:
        raise RuntimeError('Exactly nine original failed cases required')
    # Reuse the one still-retained image first, avoiding an unnecessary download.
    return ['mui__material-ui-13534'] + [key for key in failed if key != 'mui__material-ui-13534']


def repair_context(record):
    return {'saved_candidate_repair': {
        'instruction': 'Repair the complete ORIGINAL public issue from the saved candidate. '
        'First check whether the existing interpretation actually implements the requested API, '
        'defaults, input forms and lifecycle transitions. Add concrete public regressions for '
        'missed behavior and relevant existing compatibility tests. Do not merely repeat the '
        'same self-tests or change assertions to accommodate a wrong implementation. '
        'Do not invent a source change if no concrete defect is established; report limitations. '
        'Keep public feature evidence and original-source differential replay valid.',
        'prior_public_verification': record['verification']}}


def report(root, plan):
    rows, tokens, pending = [], 0, []
    for child in (root / 'tasks').glob('*'):
        part, used, active = usage(child)
        rows.extend(part)
        tokens += used
        pending.extend(active)
    ids = [r['case'] for r in rows]
    if len(ids) != len(set(ids)) or not set(ids) <= set(plan['cases']):
        raise RuntimeError('Unexpected or duplicate repair score')
    for row in rows:
        row['classification'] = classify(row)
    result = {'planned_trials': 9, 'scored_trials': len(rows),
        'complete': set(ids) == set(plan['cases']), 'rows': rows,
        'reported_tokens': tokens, 'unscored_runs': pending,
        'official_resolutions': sum(r['official_resolved'] for r in rows),
        'workflow_seconds': sum(r['seconds'] for r in rows),
        'limitation': 'Consumed-case repair attempts; not fresh benchmark accuracy or guaranteed fixes.'}
    write(root / 'results.json', result)
    return result


def budget_guard(plan, result, now, initial):
    tokens, seconds = (750000, 2400) if initial else (150000, 630)
    # usage() returns run IDs, including this controller's currently active run.
    # At a case boundary any unscored identity forbids starting another case.
    if initial and result['unscored_runs']:
        raise RuntimeError('Unscored coding identity retained; no new case admission')
    if result['reported_tokens'] + tokens > plan['max_reported_tokens'] or now + seconds >= plan['deadline']:
        raise RuntimeError('Repair budget/deadline headroom exhausted')


def run(root):
    import docker
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise RuntimeError('New root required; never restart consumed repair roots')
        assert (PARENT / 'controller.exited.json').exists()
        audit = json.loads((PARENT / 'final-audit.json').read_text())
        assert sha(PARENT / 'final-audit.json') == json.loads((PARENT / 'final-audit.lock.json').read_text())['sha256']
        keys = repair_cases(audit)
        records = {r['score']['case']: r for r in audit['records']}
        cases, seeds, old_gates = {}, {}, {}
        sealed = {str((PARENT / 'final-audit.json').resolve()): sha(PARENT / 'final-audit.json')}
        for key in keys:
            source = PARENT / 'tasks' / key
            case = json.loads((source / 'images.json').read_text())[key]
            trial = next(source.glob('experiments/heldout-results/*'))
            artifact = trial / 'state/runs' / records[key]['score']['run_id'] / 'artifacts'
            path = artifact / ('revise_1.json' if (artifact / 'revise_1.json').exists() else 'implement.json')
            seed = Candidate.model_validate_json(path.read_text())
            assert seed.candidate_commit == records[key]['score']['acceptance']['candidate_commit']
            task = runner.task_for(source, case)
            if seed.base_commit != task.base_commit:
                raise RuntimeError('Seed and original source base mismatch: ' + key)
            validate_candidate(seed, task)
            gates = source / 'preflight' / key / 'validation.json'
            assert json.loads(gates.read_text())['valid']
            case = {**case, 'execution_root': '/opt/hx-polybench-runtime/v1/' + root.name}
            cases[key], seeds[key], old_gates[key] = case, seed.model_dump(), str(gates.resolve())
            for p in [path, gates, source / 'images.json', source / 'selection.json', source / 'public' / (key + '.json')]:
                sealed[str(p.resolve())] = sha(p)
        _, _, history = prior_evidence()
        root.mkdir(parents=True)
        settings = '''adapter = "codex"
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
'''
        for key in keys:
            child = root / 'tasks' / key
            source = PARENT / 'tasks' / key
            child.mkdir(parents=True)
            for name in ['dataset.csv', 'storage.json', 'selection.json']:
                shutil.copyfile(source / name, child / name)
            storage = json.loads((child / 'storage.json').read_text(encoding='utf-8'))
            storage['execution_root'] = cases[key]['execution_root']
            write(child / 'storage.json', storage)
            shutil.copytree(source / 'public', child / 'public')
            destination = child / 'preflight' / key
            destination.mkdir(parents=True)
            shutil.copyfile(old_gates[key], destination / 'validation.json')
            write(child / 'images.json', {key: cases[key]})
            write(child / 'image-cache-policy.json', {'version': VERSION, 'retain': 1})
            write(child / 'seed-candidate.json', seeds[key])
            write(child / 'seed-public-context.json', repair_context(records[key]))
            (child / 'settings.toml').write_text(settings)
            (child / 'experiments').mkdir()
            runner.lock_sources(child)
        started = time.time()
        files = [Path(__file__), Path('scripts/run_coding_seventeen.py'),
            Path('scripts/run_lean_three.py'), Path('scripts/run_paper_benchmark.py'),
            Path('scripts/overnight_limits.py'), *Path('src/hx').glob('*.py'),
            *Path('src/hx/prompts').glob('*.md'), *Path('benchmarks/polybench').glob('*.py')]
        files += [p for p in root.rglob('*') if p.is_file()]
        files += [p for p in runner.BINARY.parent.parent.rglob('*') if p.is_file()]
        files += list((runner.VENDOR / 'src').rglob('*.py'))
        sealed.update({str(p.resolve()): sha(p) for p in files})
        plan = {'cases': keys, 'started': started, 'deadline': started + 28800,
            'max_reported_tokens': 6000000, 'per_workflow_target': 500000,
            'repair_reserve': 100000, 'max_revisions': 1, 'models': 'gpt-6.1-sol medium',
            'working_set_images': 1, 'historical_scores': history, 'sealed': sealed,
            'parent': str(PARENT), 'official_reference_receipts': old_gates,
            'scope': 'Nine explicit new consumed-development attempts seeded from accepted saved candidates. '
                     'Public evidence only. No guarantee all solutions can be fixed. No replacement of old scores.'}
        write(root / 'plan.json', plan)
        write(root / 'plan.lock.json', {'sha256': sha(root / 'plan.json')})
        write(root / 'controller.json', {'pid': os.getpid(), 'started': started, 'deadline': plan['deadline']})
        shutil.copytree('benchmarks/polybench', root / 'runtime-source/benchmarks/polybench',
            ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree('src/hx', root / 'runtime-source/src/hx', ignore=shutil.ignore_patterns('__pycache__'))
        os.environ['PATH'] = str(runner.BINARY.parent) + os.pathsep + os.environ.get('PATH', '')
        runner.report = child_report
        client = docker.from_env(timeout=600)

        def admission(initial=False, wait=False):
            while True:
                budget_guard(plan, report(root, plan), time.time(), initial)
                validate(root, plan)
                quota = account_usage(runner.BINARY, runner.AUTH)
                write(root / 'quota.json', quota)
                if can_start(quota):
                    return
                if not wait:
                    raise RuntimeError('Quota blocks repair model work')
                write(root / 'phase.json', {'phase': 'waiting_natural_quota', 'updated': time.time()})
                time.sleep(60)

        factory = partial(SeededRepair, seeds=seeds,
                          contexts={key: repair_context(records[key]) for key in keys}, admission=admission)

        try:
            register_vendor(runner.VENDOR.resolve())
            for key in keys:
                child = root / 'tasks' / key
                admission(True, True)
                write(root / 'phase.json', {'phase': 'pinned_image', 'case': key, 'updated': time.time()})
                ensure_image(client, child, cases[key])
                write(root / 'phase.json', {'phase': 'worker_preflight', 'case': key, 'updated': time.time()})
                worker_environment_check(client, cases[key], Path(cases[key]['repo_path']),
                    child / 'worker-preflight', load_settings(child / 'settings.toml'),
                    lambda: validate(root, plan), lambda *args: None)
                runner.lock_sources(child)
                admission(True, True)
                write(root / 'phase.json', {'phase': 'repair_coding', 'case': key, 'updated': time.time()})
                runner.run_case(child, key, 'lean', start_guard=lambda: admission(True), engine_factory=factory)
                write(child / 'controller.exited.json', {'case': key, 'time': time.time()})
                outcome = report(root, plan)
                print(json.dumps({'case': key, 'scored': outcome['scored_trials'],
                    'official_resolutions': outcome['official_resolutions']}), flush=True)
                if outcome['unscored_runs'] or any(r.get('usage_known') is False or r.get('grader_error') for r in outcome['rows']):
                    raise RuntimeError('Operational/unknown-usage blocker retained')
                release_images(client, [cases[key]], emit=lambda row, child=child: write(child / 'image-release.json', row))
            validate(root, plan)
            write(root / 'audit.json', {'complete': report(root, plan)['complete'],
                'historical_scores_verified': len(history),
                'scores': {str(p.relative_to(root)): sha(p) for p in root.glob('tasks/*/experiments/heldout-results/*/score.json')}})
        except BaseException as error:
            write(root / 'stop.json', {'type': type(error).__name__, 'error': str(error), 'retry_allowed': False, 'time': time.time()})
            raise
        finally:
            client.close()
            report(root, plan)
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})


if __name__ == '__main__':
    import sys
    run(Path(sys.argv[1]))
