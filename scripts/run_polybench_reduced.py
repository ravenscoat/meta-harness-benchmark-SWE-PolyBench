"""Explicit user-authorized scope amendment; frozen coding runtime stays unchanged."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.runner import lock_sources, propose, report, run_case


def prepare(root):
    directory = root / 'experiments'
    path = directory / 'scope-amendment.json'
    if path.exists():
        return
    selection = json.loads((root / 'selection.json').read_text())['cases']
    setup = [c for c in selection if c['split'] == 'setup']
    development = [c for c in selection if c['split'] == 'development']
    evaluation = [c for c in selection if c['split'] == 'evaluation']
    # Metadata-only round robin, preserving original order within each repository.
    groups = {}
    for case in evaluation:
        groups.setdefault(case['repo'], []).append(case)
    chosen = []
    for index in range(max(map(len, groups.values()))):
        for cases in groups.values():
            if index < len(cases):
                chosen.append(cases[index])
            if len(chosen) == 6:
                break
        if len(chosen) == 6:
            break
    def trials(cases, arms):
        return [{'case': c['id'], 'arm': arm} for i, c in enumerate(cases)
                for arm in arms[i % len(arms):] + arms[:i % len(arms)]]
    stages = {'setup': trials(setup, ['single']),
              'development': trials(development, ['single', 'full']),
              'tuned-development': trials(development[:8], ['tuned-sol']),
              'evaluation': trials(chosen, ['single', 'full', 'tuned-sol'])}
    tasks = sum(stages.values(), [])
    assert len(tasks) == 51
    original = json.loads((directory / 'report.json').read_text())
    expected = {(t['case'], t['arm']) for t in tasks}
    assert all((r['case'], r['arm']) in expected for r in original['rows'])
    shutil.copy2(directory / 'report.json', directory / 'report.before-scope-amendment.json')
    plan = {'authorized_change': 'User chose 44 additional trials after 7 scored; total target 51.',
            'created': time.time(), 'original_planned_trials': 95, 'planned_trials': 51,
            'scored_at_user_request': 7, 'scored_at_amendment': len(original['rows']),
            'selection_rule': 'Original development order; first8 tuned development; evaluation repository round robin in original metadata order, first6.',
            'evaluation_case_ids': [c['id'] for c in chosen], 'stages': stages,
            'source_lock_sha256': sha(directory / 'source-lock.json'),
            'original_selection_sha256': sha(root / 'selection.json'),
            'envelope_sha256': sha(directory / 'envelope.json'),
            'scheduler_sha256': sha(Path(__file__))}
    write(path, plan)
    write(directory / 'scope-amendment.lock.json', {'sha256': sha(path)})
    print(json.dumps(plan, indent=2), flush=True)


def run(root):
    directory = root / 'experiments'
    path = directory / 'scope-amendment.json'
    plan = json.loads(path.read_text())
    assert sha(path) == json.loads((directory / 'scope-amendment.lock.json').read_text())['sha256']
    assert sha(Path(__file__)) == plan['scheduler_sha256']
    assert sha(directory / 'source-lock.json') == plan['source_lock_sha256']
    assert sha(root / 'selection.json') == plan['original_selection_sha256']
    assert sha(directory / 'envelope.json') == plan['envelope_sha256']
    lock_sources(root)
    limits = json.loads((directory / 'envelope.json').read_text())
    expected = {(t['case'], t['arm']) for tasks in plan['stages'].values() for t in tasks}

    def summary():
        value = report(root)
        assert all((r['case'], r['arm']) in expected for r in value['rows'])
        value.update(planned_trials=51, original_planned_trials=95,
                     scope_amendment='scope-amendment.json', complete=len(value['rows']) == 51)
        write(directory / 'report.json', value)
        text = (directory / 'REPORT.md').read_text()
        text = text.replace('/95 (5 setup, 30 development, 60 evaluation)',
                            '/51 (5 setup, 28 development, 18 evaluation; amended from95)')
        (directory / 'REPORT.md').write_text(text)
        return value

    def boundary():
        if (directory / 'stop-after-case').exists():
            raise RuntimeError('Operator stop at scored boundary')
        value = summary()
        tokens = sum(r['observed_tokens'] for r in value['rows']) + value['proposer_tokens']
        if tokens >= limits['max_observed_tokens'] or time.time() - limits['started'] >= limits['max_seconds']:
            raise RuntimeError('Original campaign envelope exhausted')
        return {(r['case'], r['arm']) for r in value['rows']}

    for stage, tasks in plan['stages'].items():
        if stage == 'tuned-development':
            boundary()
            propose(root)
        for task in tasks:
            done = boundary()
            if (task['case'], task['arm']) in done:
                continue
            result = run_case(root, task['case'], task['arm'])
            summary()
            message = (result['error'] or '').lower()
            if result['grader_error'] or any(s in message for s in
                    ['usage limit', 'rate limit', 'websocket', 'authentication', 'sandbox setup',
                     'container command failed', 'container codex exited']):
                raise RuntimeError('Operational failure; retained trial, scheduling stopped')
    value = summary()
    assert value['complete']
    write(directory / 'complete.json', {'finished': time.time(), 'total_task_trials': 51,
          'evaluation_trials': 18, 'original_planned_trials': 95, 'scope_amendment': 'scope-amendment.json'})
    print(json.dumps({'event': 'campaign.complete', 'task_trials': 51}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    os.environ['PATH'] = '/opt/hx-codex/node_modules/.bin:' + os.environ['PATH']
    if args.prepare:
        prepare(args.root.resolve())
    else:
        run(args.root.resolve())
