"""One remaining unused pinned evaluation task after natural quota reset."""
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

CASE = 'mui__material-ui-22696'
SOURCE = Path('.hx/polybench-v1')
ARCHIVE = Path('.hx/worker-loop-runtime-v14')


def history():
    patterns = ['*/experiments/*/*/score.json',
                'parallel-three-v1/tasks/*/experiments/*/*/score.json']
    return {str(p.resolve()): sha(p) for pattern in patterns for p in Path('.hx').glob(pattern)}


def prepare(root, not_before):
    if root.exists():
        raise RuntimeError('New identity required; never prepare existing evidence')
    historical = history()
    if any(json.loads(Path(p).read_text()).get('case',
           json.loads(Path(p).read_text()).get('instance_id')) == CASE for p in historical):
        raise RuntimeError('Selected task already scored')
    for pattern in ['*/experiments/*/*/state/native-state.json',
                    'parallel-three-v1/tasks/*/experiments/*/*/state/native-state.json']:
        if any(CASE in str(p) for p in Path('.hx').glob(pattern)):
            raise RuntimeError('Selected task has a consumed coding identity')
    for p in Path('.hx').glob('*/exposure.json'):
        if CASE in json.loads(p.read_text()).get('cases', []):
            raise RuntimeError('Selected task has explicit recorded exposure')
    selection = json.loads((SOURCE/'selection.json').read_text())
    cases = [c for c in selection['cases'] if c['id'] == CASE and c['split'] == 'evaluation']
    if len(cases) != 1:
        raise RuntimeError('Expected original evaluation metadata')
    images = json.loads((SOURCE/'images.json').read_text())
    gate = json.loads((SOURCE/'preflight'/CASE/'validation.json').read_text())
    if not gate['valid'] or gate['image_id'] != images[CASE]['image_id']:
        raise RuntimeError('Pinned environment validation mismatch')
    select_for_experiment(root, ARCHIVE)
    for name in ['dataset.csv', 'storage.json']:
        shutil.copyfile(SOURCE/name, root/name)
    shutil.copyfile('.hx/remaining-quota-benchmark-v1/settings.toml', root/'settings.toml')
    settings = load_settings(root/'settings.toml')
    if settings.worker_model != 'gpt-6.1-sol' or settings.max_revisions != 1:
        raise RuntimeError('Expected Sol worker and one repair')
    write(root/'selection.json', {**selection, 'cases': cases})
    write(root/'images.json', {CASE: images[CASE]})
    for directory, name in [('public', CASE+'.json'), ('preflight/'+CASE, 'validation.json')]:
        (root/directory).mkdir(parents=True)
        shutil.copyfile(SOURCE/directory/name, root/directory/name)
    (root/'experiments').mkdir()
    now = time.time()
    # A new, explicit envelope includes the observed natural-reset wait.
    # It never extends or resumes any old campaign.
    if not_before < now or not_before > now + 18000:
        raise RuntimeError('Expected bounded future natural reset')
    input_names = ['dataset.csv', 'storage.json', 'settings.toml', 'selection.json', 'images.json',
                   'worker-scaffold.py', 'worker-scaffold.lock.json', 'public/'+CASE+'.json',
                   'preflight/'+CASE+'/validation.json']
    plan = {'cases': [CASE], 'started': now, 'not_before': not_before,
        'deadline': not_before+10800, 'max_trials': 1, 'max_reported_tokens': 1200000,
        'worker': 'gpt-6.1-sol', 'protocol': VERSION, 'max_revisions': 1,
        'per_workflow_target': 900000, 'repair_reserve': 150000,
        'quota_limits': {'primary_exclusive': 80, 'weekly_exclusive': 90},
        'authorization': 'User authorized benchmark execution and accepts unresolved tasks. One remaining unused original evaluation task; no model work near quota limits.',
        'selection_rule': 'Only unused original validated evaluation case after score/native-state/exposure exclusion. No outcome ranking or substitution.',
        'historical_score_sha256': historical,
        'scheduler_sha256': {str(p.resolve()): sha(p) for p in [Path(__file__),
            Path(single.__file__), Path('scripts/overnight_limits.py'),
            Path('scripts/run_paper_benchmark.py'), ARCHIVE/'archive-lock.json',
            *[root/name for name in input_names]]},
        'limitations': 'One task in a known repository; same-model independent test author and implementer. Public tests do not establish official resolution. No paired gain or leaderboard inference. Turn-boundary usage can overshoot. No purchases/reset credits/private grader or accepted solutions in worker context.'}
    write(root/'batch-plan.json', plan)
    write(root/'batch-plan.lock.json', {'sha256': sha(root/'batch-plan.json')})
    runner.lock_sources(root)


def report(root, plan):
    from scripts.run_paper_benchmark import usage
    rows, tokens, incomplete = usage(root)
    value = {'planned_trials': 1, 'scored': len(rows), 'complete': len(rows) == 1,
             'rows': rows, 'reported_tokens': tokens, 'retained_unscored_runs': incomplete,
             'limitations': plan['limitations']}
    write(root/'results.json', value)
    write(root/'experiments/report.json', value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--not-before', type=float, default=0)
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:'+os.environ['PATH']
    root = args.root.resolve()
    if args.prepare:
        prepare(root, args.not_before)
    plan = json.loads((root/'batch-plan.json').read_text())
    if plan['cases'] != [CASE] or plan['quota_limits'] != {'primary_exclusive': 80, 'weekly_exclusive': 90}:
        raise RuntimeError('Unexpected fixed task or quota limits')
    single.CASE = CASE
    single.report = report
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
