"""Task 3 evidenced keyed-each codegen compatibility repair."""
import json
import os
import shutil
import time
from functools import partial
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.image_cache import VERSION, ensure_image
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.config import load_settings
from hx.git import validate_candidate
from hx.models import Candidate
from scripts.overnight_limits import account_usage, can_start
from scripts.run_coding_seventeen import child_report, validate
from scripts.run_lean_three import prior_evidence
from scripts.run_paper_benchmark import usage
from scripts.run_solution_repairs import SeededRepair, budget_guard

KEY = 'sveltejs__svelte-4558'
PARENT = Path('.hx/solution-repairs-v1')
ORIGINAL = Path('.hx/coding-seventeen-v1')
BADGE = Path('.hx/badge-contract-repair-v1')
TREEVIEW = Path('.hx/treeview-api-repair-v1')
SEVEN = PARENT / 'seven-task-amendment.json'
PREVIOUS = Path('.hx/svelte-keyed-repair-v1')
NOTES = Path('.hx/svelte-keyed-codegen-notes-v1.json')
DIAGNOSTIC = Path('.hx/svelte-keyed-public-diagnostic-v1')


def run(root):
    import docker
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise RuntimeError('New root required; never restart a consumed identity')
        if not (PARENT / 'controller.exited.json').exists():
            raise RuntimeError('Parent must be stopped')
        parent = json.loads((PARENT / 'plan.json').read_text())
        validate(PARENT, parent)
        amendment = json.loads(SEVEN.read_text())
        if sha(SEVEN) != json.loads(SEVEN.with_name('seven-task-amendment.lock.json').read_text())['sha256']:
            raise RuntimeError('Seven-task scope lock mismatch')
        if KEY != amendment['cases'][2] or amendment['authorized_total'] != 7:
            raise RuntimeError('Task3 must match locked seven-task scope')
        completed = [PARENT, BADGE, Path('.hx/treeview-contract-repair-v1'), TREEVIEW, PREVIOUS]
        for previous in completed:
            if not (previous / 'controller.exited.json').exists():
                raise RuntimeError('Earlier controllers must be stopped')
        passed_scores = []
        for previous in (BADGE, TREEVIEW):
            scores = list(previous.glob('experiments/heldout-results/*/score.json'))
            if len(scores) != 1 or not json.loads(scores[0].read_text())['official_resolved']:
                raise RuntimeError('Tasks1and2 must officially pass before task3')
            passed_scores.extend(scores)
        parts = [json.loads((previous / 'results.json').read_text()) for previous in completed]
        if any(part.get('unscored_runs') for part in parts):
            raise RuntimeError('Earlier interrupted identities block new coding')
        spent = sum(part['reported_tokens'] for part in parts)
        if not (DIAGNOSTIC / 'exited.json').exists():
            raise RuntimeError('Public diagnostic must stop before new coding')
        validate(PREVIOUS, json.loads((PREVIOUS / 'plan.json').read_text()))
        source = PREVIOUS
        case = json.loads((source / 'images.json').read_text())[KEY]
        trial = next(source.glob('experiments/heldout-results/*'))
        score = json.loads((trial / 'score.json').read_text())
        artifacts = trial / 'state/runs' / score['run_id'] / 'artifacts'
        seed_path = artifacts / ('revise_1.json' if (artifacts / 'revise_1.json').exists() else 'implement.json')
        seed = Candidate.model_validate_json(seed_path.read_text())
        score = json.loads(next(source.glob('experiments/heldout-results/*/score.json')).read_text())
        assert seed.candidate_commit == score['acceptance']['candidate_commit']
        task = runner.task_for(source, case)
        assert seed.base_commit == task.base_commit
        validate_candidate(seed, task)
        notes = json.loads(NOTES.read_text())
        _, _, history = prior_evidence()
        root.mkdir(parents=True)
        for name in ['dataset.csv', 'selection.json', 'settings.toml']:
            shutil.copyfile(source / name, root / name)
        shutil.copyfile(PARENT / 'tasks' / KEY / 'settings.toml', root / 'settings.toml')
        shutil.copytree(source / 'public', root / 'public')
        shutil.copytree(source / 'preflight', root / 'preflight')
        case['execution_root'] = '/opt/hx-polybench-runtime/v1/' + root.name
        storage = json.loads((source / 'storage.json').read_text())
        storage['execution_root'] = case['execution_root']
        write(root / 'storage.json', storage)
        write(root / 'images.json', {KEY: case})
        write(root / 'image-cache-policy.json', {'version': VERSION, 'retain': 1})
        write(root / 'seed-candidate.json', seed.model_dump())
        context = {'public_specification_repair': notes,
                   'instruction': 'Repair the concretely observed keyed-each codegen compatibility gap, not just tests. Original public compiler fixtures for keyed blocks without else must retain their intended output while keyed else runtime transitions work. Do not regenerate expectations to conceal an unnecessarily broad generator change. Add targeted boundary regression for scope of generator change and exact-delivery runtime compatibility. Use focused original-source witnesses separate from broad legacy runner failure-followup skips; never weaken the classifier. Public custom-element browser setup errors are separate and remain disclosed. No private evaluator content is available.'}
        write(root / 'seed-public-context.json', context)
        (root / 'experiments').mkdir()
        runner.lock_sources(root)
        files = [*Path('benchmarks/polybench').glob('*.py'), *Path('src/hx').glob('*.py'),
                 *Path('src/hx/prompts').glob('*.md'), Path(__file__),
                 Path('scripts/run_solution_repairs.py'), Path('scripts/run_coding_seventeen.py'),
                 Path('scripts/overnight_limits.py'), Path('scripts/run_lean_three.py'),
                 Path('scripts/run_paper_benchmark.py'), Path('scripts/capture_public_issue_context.py'),
                 seed_path, NOTES, DIAGNOSTIC / 'public-summary.json',
                 PREVIOUS / 'final-audit.json', SEVEN, SEVEN.with_name('seven-task-amendment.lock.json'),
                 *passed_scores, *[previous / 'results.json' for previous in completed],
                 *[p for p in root.rglob('*') if p.is_file()]]
        for original in list(files):
            if original.parts[0] in {'scripts', 'src', 'benchmarks'}:
                target = root / 'runtime-source' / original
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                files.append(target)
        plan = {'cases': [KEY], 'deadline': parent['deadline'],
                'max_reported_tokens': parent['max_reported_tokens'], 'prior_reported_tokens': spent,
                'started': time.time(), 'historical_scores': history,
                'sealed': {str(p.resolve()): sha(p) for p in files},
                'parent_plan_sha256': sha(PARENT / 'plan.json'),
                'scope': 'Task 3 of locked seven: public-evidenced Svelte codegen compatibility repair. '
                'No fresh heldout, causal improvement or automatic advancement claim.'}
        write(root / 'plan.json', plan)
        write(root / 'plan.lock.json', {'sha256': sha(root / 'plan.json')})
        write(root / 'controller.json', {'pid': os.getpid(), 'started': time.time(), 'deadline': plan['deadline']})
        client = docker.from_env(timeout=600)
        runner.report = child_report
        os.environ['PATH'] = str(runner.BINARY.parent) + os.pathsep + os.environ.get('PATH', '')

        def admission(initial=False):
            while True:
                rows, used, pending = usage(root)
                budget_guard(plan, {'reported_tokens': spent + used, 'unscored_runs': pending}, time.time(), initial)
                validate(root, plan)
                quota = account_usage(runner.BINARY, runner.AUTH)
                write(root / 'quota.json', quota)
                if can_start(quota):
                    return
                known = all(isinstance(quota.get(window, {}).get('usedPercent'), (int, float))
                            and 0 <= quota[window]['usedPercent'] <= 100
                            for window in ('primary', 'secondary'))
                if not initial or not quota.get('ordinary_allowed') or not known:
                    raise RuntimeError('Quota unavailable or blocks worker; preserve identity')
                write(root / 'phase.json', {'phase': 'waiting_natural_quota', 'case': KEY, 'time': time.time()})
                time.sleep(min(300, max(1, plan['deadline'] - time.time() - 2400)))

        factory = partial(SeededRepair, seeds={KEY: seed.model_dump()},
                          contexts={KEY: context}, admission=admission)
        try:
            admission(True)
            write(root / 'phase.json', {'phase': 'pinned_image', 'case': KEY, 'time': time.time()})
            ensure_image(client, root, case)
            write(root / 'phase.json', {'phase': 'worker_preflight', 'case': KEY, 'time': time.time()})
            worker_environment_check(client, case, Path(case['repo_path']), root / 'worker-preflight',
                                     load_settings(root / 'settings.toml'), lambda: validate(root, plan), lambda *a: None)
            admission(True)
            write(root / 'phase.json', {'phase': 'coding_repair', 'case': KEY, 'time': time.time()})
            runner.run_case(root, KEY, 'lean', start_guard=lambda: admission(True), engine_factory=factory)
            validate(root, plan)
            write(root / 'audit.json', {'complete': child_report(root)['complete'],
                  'historical_score_files_verified': len(history), 'parent_tokens': spent,
                  'scores': {str(p.relative_to(root)): sha(p) for p in root.glob('experiments/heldout-results/*/score.json')}})
        except BaseException as error:
            write(root / 'stop.json', {'type': type(error).__name__, 'error': str(error), 'retry_allowed': False})
            raise
        finally:
            client.close()
            write(root / 'results.json', child_report(root))
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})


if __name__ == '__main__':
    import sys
    run(Path(sys.argv[1]))
