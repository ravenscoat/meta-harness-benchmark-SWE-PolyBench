"""One new consumed task attempt after complete offline replay validation."""
import argparse
import json
import os
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.independent import IndependentEngine
from benchmarks.polybench.prepare import sha, write
from scripts import run_label_repair_benchmark as parent
from scripts import run_one_react_benchmark as single


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    root = args.root.resolve()
    if args.prepare:
        replay = json.loads(Path('.hx/report-ingestion-repair-v1/replay.json').read_text())
        if len(replay['results']) != 2 or not all(row['offline_actual_replay_passed'] for row in replay['results']):
            raise RuntimeError('Both complete offline public replays must pass before model work')
        parent.SEARCH = Path('.hx/worker-loop-runtime-v8')
        parent.prepare(root)
        plan = json.loads((root / 'batch-plan.json').read_text())
        plan['repair'] = 'public-base-regression@6 complete bounded public-log ingestion'
        plan['scheduler_sha256'].update({str(p.resolve()): sha(p) for p in [Path(__file__),
            Path('.hx/report-ingestion-repair-v1/replay.json'), Path('.hx/report-ingestion-repair-v1/replay.py')]})
        write(root / 'batch-plan.json', plan)
        write(root / 'batch-plan.lock.json', {'sha256': sha(root / 'batch-plan.json')})
    single.CASE = parent.parent.CASE
    single.report = parent.parent.report
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
