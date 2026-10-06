"""One consumed MUI attempt after complete report-capture replay validation."""
import argparse
import json
import os
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.independent import IndependentEngine
from benchmarks.polybench.prepare import sha, write
from scripts import run_label_repair_benchmark as parent
from scripts import run_one_react_benchmark as single


def prepare(root):
    evidence = Path('.hx/report-capture-repair-v1')
    replay = json.loads((evidence / 'replay.json').read_text())
    integrity = json.loads((evidence / 'integrity.json').read_text())
    audit = json.loads((evidence / 'audit.json').read_text(encoding='utf-8-sig'))
    if len(replay['results']) != 3 or not all(
        row['offline_actual_replay_passed'] for row in replay['results']
    ):
        raise RuntimeError('All three frozen public capture replays must pass')
    if integrity['historical_scores_unchanged'] != 104:
        raise RuntimeError('Expected preserved historical evidence')
    for name, expected in audit['hashes'].items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Capture repair evidence changed: ' + name)
    parent.SEARCH = Path('.hx/worker-loop-runtime-v9')
    parent.prepare(root)
    plan = json.loads((root / 'batch-plan.json').read_text())
    plan['repair'] = 'public-base-regression@7 file-backed complete JSON capture'
    plan['parent_attempt'] = '.hx/report-repair-benchmark-v1'
    plan['scheduler_sha256'].update({str(p.resolve()): sha(p) for p in [
        Path(__file__), evidence / 'replay.json', evidence / 'integrity.json',
        evidence / 'audit.json',
    ]})
    write(root / 'batch-plan.json', plan)
    write(root / 'batch-plan.lock.json', {'sha256': sha(root / 'batch-plan.json')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    root = args.root.resolve()
    if args.prepare:
        prepare(root)
    single.CASE = parent.parent.CASE
    single.report = parent.parent.report
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
