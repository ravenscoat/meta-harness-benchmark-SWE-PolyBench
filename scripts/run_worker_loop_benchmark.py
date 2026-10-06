"""One locked React benchmark attempt using the executable worker scaffold."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.independent import VERSION, IndependentEngine
from benchmarks.polybench.prepare import sha, write
from hx.config import load_settings
from scripts import run_one_react_benchmark as single
from scripts.worker_scaffold_search import select_for_experiment

CASE = 'mui__material-ui-18141'
OLD = Path('.hx/polybench-v1')
SEARCH = Path('.hx/worker-loop-runtime-v6')
BASE_REPORT = single.report


def prepare(root, not_before):
    if root.exists():
        raise RuntimeError('New benchmark identity required')
    single.CASE = CASE
    historical = single.history()
    single.validate_fresh(historical)
    select_for_experiment(root, SEARCH)
    for name in ('dataset.csv', 'storage.json'):
        shutil.copyfile(OLD / name, root / name)
    settings = Path('.hx/independent-three-v2/settings.toml')
    shutil.copyfile(settings, root / 'settings.toml')
    selected = json.loads((OLD / 'selection.json').read_text())
    selected['cases'] = [row for row in selected['cases'] if row['id'] == CASE]
    if len(selected['cases']) != 1 or selected['cases'][0]['split'] != 'evaluation':
        raise RuntimeError('Pinned evaluation identity missing')
    write(root / 'selection.json', selected)
    images = json.loads((OLD / 'images.json').read_text())
    write(root / 'images.json', {CASE: images[CASE]})
    for directory, name in [('public', CASE + '.json'), ('preflight/' + CASE, 'validation.json')]:
        (root / directory).mkdir(parents=True)
        shutil.copyfile(OLD / directory / name, root / directory / name)
    (root / 'experiments').mkdir()
    started = time.time()
    if not_before + 2400 >= started + 14400:
        raise RuntimeError('Reset leaves insufficient workflow window')
    plan = {'cases': [CASE], 'started': started, 'not_before': not_before,
        'deadline': started + 14400, 'max_trials': 1, 'max_reported_tokens': 1000000,
        'per_trial_reported_token_target': load_settings(root / 'settings.toml').max_observed_tokens,
        'worker': 'gpt-6.1-sol', 'workflow': 'single', 'independent_challenge': VERSION,
        'selection_rule': 'First unused React case in original pinned evaluation order; no outcome filtering.',
        'rule': 'One fresh coding attempt, one public-feedback repair, no replacements, resets or purchases. Turn-boundary caps may overshoot.',
        'limitations': 'One task in a familiar repository, no paired baseline or causal improvement claim. Separate same-model test author may share errors.',
        'historical_score_sha256': historical,
        'scheduler_sha256': {str(p.resolve()): sha(p) for p in [Path(__file__), Path(single.__file__),
            Path('scripts/overnight_limits.py'), Path('scripts/run_paper_benchmark.py'),
            Path('scripts/worker_scaffold_search.py'), settings,
            SEARCH / 'archive-lock.json']}}
    write(root / 'batch-plan.json', plan)
    write(root / 'batch-plan.lock.json', {'sha256': sha(root / 'batch-plan.json')})
    runner.lock_sources(root)


def report(root, plan):
    value = BASE_REPORT(root, plan)
    value['limitations'] = plan['limitations']
    value['scaffold_sha256'] = json.loads((root / 'worker-scaffold.lock.json').read_text())['sha256']
    write(root / 'results.json', value)
    write(root / 'experiments/report.json', value)
    (root / 'experiments/REPORT.md').write_text('# One executable-loop benchmark: MUI 18141\n\n' +
        json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--not-before', type=float, default=0)
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    root = args.root.resolve()
    single.CASE = CASE
    if args.prepare:
        prepare(root, args.not_before)
    single.report = report
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
