"""One new Svelte477 consumed-development attempt after runtime-error repair."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.independent import IndependentEngine
from benchmarks.polybench.prepare import sha, write
from scripts import run_one_react_benchmark as single
from scripts.run_remaining_quota_benchmark import can_start_remaining
from scripts.worker_scaffold_search import select_for_experiment

CASE = 'sveltejs__svelte-477'
OLD = Path('.hx/parallel-three-v1/tasks') / CASE
EVIDENCE = Path('.hx/runtime-exception-classifier-repair-v1')
BASE_REPORT = single.report


def prepare(root):
    if root.exists():
        raise RuntimeError('New Svelte attempt identity required')
    audit = json.loads((EVIDENCE / 'audit.json').read_text(encoding='utf-8-sig'))
    if audit['status'] != 'verified_classifier_repair':
        raise RuntimeError('Actual offline repair validation required')
    validation = json.loads((EVIDENCE / 'validation.json').read_text())
    for name, expected in validation['sha256'].items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Repair evidence changed: ' + name)
    select_for_experiment(root, Path('.hx/worker-loop-runtime-v11'))
    for name in ['dataset.csv', 'storage.json', 'selection.json', 'images.json', 'settings.toml']:
        shutil.copyfile(OLD / name, root / name)
    for directory in ['public', 'preflight']:
        shutil.copytree(OLD / directory, root / directory)
    (root / 'experiments').mkdir()
    historical = json.loads((EVIDENCE / 'historical-score-lock.json').read_text())
    for name, expected in historical.items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Historical score changed')
    now = time.time()
    plan = {'cases': [CASE], 'started': now, 'not_before': 0,
        'deadline': now + 10800, 'max_trials': 1, 'max_reported_tokens': 1200000,
        'per_trial_reported_token_target': 900000, 'worker': 'gpt-6.1-sol',
        'workflow': 'single', 'parent_attempt': '.hx/svelte477-repair-benchmark-v1',
        'runtime_version': 'public-base-regression@8',
        'quota_limits': {'primary_exclusive': 80, 'weekly_exclusive': 98},
        'rule': 'One new user-authorized consumed Svelte attempt; one repair. No rerun, replacement, purchases, resets or private grader/solution context. Turn-boundary overshoot possible.',
        'limitations': 'Consumed development task after verified public runtime-exception classification repair; not fresh heldout or paired causal improvement. Same model separate blind author and implementer contexts.',
        'historical_score_sha256': historical,
        'scheduler_sha256': {str(p.resolve()): sha(p) for p in [Path(__file__),
            Path(single.__file__), Path('scripts/run_remaining_quota_benchmark.py'),
            Path('scripts/overnight_limits.py'), Path('scripts/run_paper_benchmark.py'),
            EVIDENCE / 'audit.json', EVIDENCE / 'validation.json',
            Path('.hx/worker-loop-runtime-v11/archive-lock.json')]}}
    write(root / 'batch-plan.json', plan)
    write(root / 'batch-plan.lock.json', {'sha256': sha(root / 'batch-plan.json')})
    runner.lock_sources(root)


def report(root, plan):
    value = BASE_REPORT(root, plan)
    value['limitations'] = plan['limitations']
    write(root / 'results.json', value)
    write(root / 'experiments/report.json', value)
    (root / 'experiments/REPORT.md').write_text('# Svelte477 repaired-classifier attempt\n\n'
        + json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    root = args.root.resolve()
    if args.prepare:
        prepare(root)
    plan = json.loads((root / 'batch-plan.json').read_text())
    if plan['cases'] != [CASE] or plan['quota_limits'] != {'primary_exclusive': 80, 'weekly_exclusive': 98}:
        raise RuntimeError('Expected authorized one-task plan')
    single.CASE = CASE
    single.report = report
    single.can_start = can_start_remaining
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
