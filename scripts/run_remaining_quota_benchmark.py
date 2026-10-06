"""One explicitly authorized MUI attempt using the remaining weekly allowance."""
import argparse
import json
import os
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.independent import IndependentEngine
from benchmarks.polybench.prepare import sha, write
from scripts import run_capture_repair_benchmark as capture
from scripts import run_one_react_benchmark as single


def can_start_remaining(quota):
    """This new envelope only; older campaigns keep their original 90% guard."""
    return (quota['ordinary_allowed'] and quota['primary']['usedPercent'] < 80
            and quota['secondary']['usedPercent'] < 98)


def prepare(root):
    capture.prepare(root)
    plan = json.loads((root / 'batch-plan.json').read_text())
    plan['quota_authorization'] = (
        'User explicitly requested one question using remaining 10 percent; '
        'weekly stop threshold 98 percent for this new identity only. '
        'No purchases or reset credits; ordinary usage must remain allowed.'
    )
    plan['quota_limits'] = {'primary_used_percent_exclusive': 80,
                            'weekly_used_percent_exclusive': 98}
    plan['stopped_parent'] = '.hx/capture-repair-benchmark-v1'
    plan['scheduler_sha256'][str(Path(__file__).resolve())] = sha(Path(__file__))
    plan['scheduler_sha256'][str(Path(capture.__file__).resolve())] = sha(Path(capture.__file__))
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
    plan = json.loads((root / 'batch-plan.json').read_text())
    if plan.get('quota_limits') != {'primary_used_percent_exclusive': 80,
                                    'weekly_used_percent_exclusive': 98}:
        raise RuntimeError('Explicit remaining-quota plan is required')
    single.CASE = capture.parent.parent.CASE
    single.report = capture.parent.parent.report
    single.can_start = can_start_remaining
    runner.PolyEngine = IndependentEngine
    single.run(root)


if __name__ == '__main__':
    main()
