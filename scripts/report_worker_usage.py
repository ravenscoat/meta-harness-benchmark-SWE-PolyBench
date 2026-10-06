"""Read public worker JSONL only; no private evaluator data or model calls."""
import argparse
import json
import re
from pathlib import Path

from hx.usage import usage_breakdown


def report(root):
    calls = []
    paths = set(root.glob('tasks/*/experiments/heldout-results/*/state/runs/*/steps/*/attempt-*/**/stdout.txt'))
    paths.update(root.glob('experiments/heldout-results/*/state/runs/*/steps/*/attempt-*/**/stdout.txt'))
    for path in sorted(paths):
        turns = []
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get('type') == 'turn.completed':
                turns.append(usage_breakdown(event.get('usage')))
        if not turns:
            continue
        parts = path.relative_to(root).parts
        step = parts[parts.index('steps') + 1]
        trial = parts[parts.index('heldout-results') + 1]
        match = re.fullmatch(r'(?:full|single|lean|tuned-sol)-(.+)-\d+', trial)
        case = parts[1] if parts[0] == 'tasks' else match[1] if match else trial
        calls.append({'path': str(path.relative_to(root)), 'case': case, 'step': step,
                      'role': 'test_author' if step == 'independent_challenge' else
                              'repair' if step.startswith('revise_') else 'implementer',
                      'turns': turns})
    groups = {}
    for call in calls:
        group = groups.setdefault(call['role'], {'completed_turns': 0, 'reported_tokens': 0,
            'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0,
            'uncached_input_tokens': 0, 'unknown_usage_turns': 0, 'unknown_cache_turns': 0})
        for turn in call['turns']:
            group['completed_turns'] += 1
            for field in ['reported_tokens', 'input_tokens', 'output_tokens',
                          'cached_input_tokens', 'uncached_input_tokens']:
                group[field] += turn[field] or 0
            group['unknown_usage_turns'] += not turn['usage_known']
            group['unknown_cache_turns'] += not turn['cache_usage_known']
    return {'root': str(root), 'roles': groups, 'calls': calls, 'monetary_cost': None,
            'limitation': 'Completed-turn reports only; missing/interrupted usage is not zero. '
                          'Cached input is included in input. No monetary cost inferred.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = json.dumps(report(args.root), indent=2) + '\n'
    if args.output:
        if args.output.exists():
            raise SystemExit('Refusing to overwrite an existing usage report')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding='utf-8')
    else:
        print(value)
