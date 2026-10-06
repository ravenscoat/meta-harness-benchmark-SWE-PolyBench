"""One explicitly authorized new development attempt after label classification repair."""
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
from scripts import run_worker_loop_benchmark as parent
from scripts.worker_scaffold_search import select_for_experiment

OLD = Path('.hx/worker-loop-benchmark-v1')
SEARCH = Path('.hx/worker-loop-runtime-v7')


def prepare(root):
    if root.exists():
        raise RuntimeError('New development identity required')
    replay = json.loads(Path('.hx/label-classifier-repair-v1/saved-public-replay.json').read_text())
    if replay['new_category'] != 'behavioral_failure':
        raise RuntimeError('Saved public replay repair not validated')
    select_for_experiment(root, SEARCH)
    for name in ['dataset.csv', 'storage.json', 'images.json', 'selection.json', 'settings.toml']:
        shutil.copyfile(OLD / name, root / name)
    # Same task is now consumed development evidence. Original heldout score remains intact.
    selected = json.loads((root / 'selection.json').read_text())
    selected['cases'][0]['split'] = 'development'
    write(root / 'selection.json', selected)
    settings = (root / 'settings.toml').read_text()
    (root / 'settings.toml').write_text(settings.replace('max_observed_tokens = 700000', 'max_observed_tokens = 900000'))
    for directory in ['public', 'preflight']:
        shutil.copytree(OLD / directory, root / directory)
    (root / 'experiments').mkdir()
    started = time.time()
    plan = {'cases': [parent.CASE], 'started': started, 'not_before': 0,
        'deadline': started + 10800, 'max_trials': 1, 'max_reported_tokens': 1200000,
        'per_trial_reported_token_target': 900000, 'worker': 'gpt-6.1-sol', 'workflow': 'single',
        'rule': 'One new consumed development identity, one public-feedback repair; no silent retries or score replacement. Turn caps can overshoot. No purchases or resets.',
        'limitations': 'Consumed task and prior public reproduction inspected; development diagnostic, not fresh heldout or paired improvement. Larger token target preserves initial-implementation headroom after authoring.',
        'historical_score_sha256': single.history(),
        'scheduler_sha256': {str(p.resolve()): sha(p) for p in [Path(__file__), Path(parent.__file__),
            Path(single.__file__), Path('scripts/overnight_limits.py'), Path('scripts/run_paper_benchmark.py'),
            SEARCH / 'archive-lock.json', OLD / 'batch-plan.json', OLD / 'score-lock.json']}}
    write(root / 'batch-plan.json', plan)
    write(root / 'batch-plan.lock.json', {'sha256': sha(root / 'batch-plan.json')})
    runner.lock_sources(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    root = args.root.resolve()
    if args.prepare:
        prepare(root)
    single.CASE = parent.CASE
    single.report = parent.report
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
