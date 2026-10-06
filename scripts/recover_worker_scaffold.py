"""Separate zero-model validation of a complete logged worker-loop draft."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from hx.code_search import CodeProposal, seal, sha
from hx.config import canonical
from hx.models import HXError
from hx.process import clean_env
from hx.store import atomic_write
from hx.worker_scaffold import validate_scaffold
from scripts.worker_scaffold_search import GATES, exercise_scaffold


def logged_source(path):
    complete = []
    for line in path.read_text().splitlines():
        event = json.loads(line)
        item = event.get('item', {})
        if (item.get('type') == 'command_execution' and item.get('status') == 'completed'
                and item.get('exit_code') == 0
                and item.get('command') == "/bin/bash -lc 'cat candidate_scaffold.py'"):
            complete.append(item['aggregated_output'].encode())
    if not complete:
        raise HXError('No complete exact-target source observation; do not recover partial drafts')
    validate_scaffold(complete[-1])
    return complete[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    original, root = args.original.resolve(), args.root.resolve()
    archive_path = original / 'archive-lock.json'
    archive = json.loads(archive_path.read_text())['files']
    if {k: v for k, v in seal(original).items() if k != 'archive-lock.json'} != archive:
        raise HXError('Original search archive changed')
    if root.exists():
        raise HXError('New recovery identity required')
    root.mkdir(parents=True)
    original_archive_hash = sha(archive_path.read_bytes())
    try:
        source = logged_source(original / 'sol/stdout.txt')
        atomic_write(root / 'candidate.py', source)
        proposals, usage = [], 0
        for line in (original / 'sol/stdout.txt').read_text().splitlines():
            event = json.loads(line)
            if event.get('type') == 'turn.completed':
                tokens = event.get('usage', {})
                usage += tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)
            item = event.get('item', {})
            if item.get('type') == 'agent_message':
                try:
                    proposals.append(CodeProposal.model_validate_json(item['text']).model_dump())
                except ValueError:
                    pass
        if not proposals:
            raise HXError('No completed schema-valid proposer summary')
        atomic_write(root / 'proposal.json', canonical(proposals[-1]))
        plan = json.loads((original / 'plan.json').read_text())
        if not all(sha(Path(p).read_bytes()) == h for p, h in plan['historical_scores'].items()):
            raise HXError('Historical score changed')
        with tempfile.TemporaryDirectory(prefix='hx-loop-recovery-',
                dir='/opt/hx-polybench-runtime/v1/infra-checks') as temp:
            native = Path(temp)
            fixture = exercise_scaffold(root / 'candidate.py', native / 'fixture')
            # Preserve fixture execution records, not its temporary absolute paths.
            import shutil
            shutil.copytree(native / 'fixture', root / 'fixture', ignore=shutil.ignore_patterns('__pycache__'))
            result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                *GATES, '--basetemp=' + str(native / 'gates')], capture_output=True,
                timeout=180, env=clean_env())
            atomic_write(root / 'gates.stdout.txt', result.stdout)
            atomic_write(root / 'gates.stderr.txt', result.stderr)
        if sha(archive_path.read_bytes()) != original_archive_hash:
            raise HXError('Original archive modified during recovery')
        atomic_write(root / 'candidate-ready.json', canonical({
            'eligible_for_task_experiment': fixture and result.returncode == 0,
            'sha256': sha(source), 'real_fixture_verified': fixture,
            'regressions_passed': result.returncode == 0, 'coding_performance_promoted': False,
            'model_calls': 0, 'original_reported_tokens_from_completed_turns': usage,
            'original_archive_sha256': original_archive_hash,
            'original_trace_sha256': sha((original / 'sol/stdout.txt').read_bytes()),
            'historical_scores_unchanged': len(plan['historical_scores']),
            'limitations': 'Original proposal remains budget-failed. Exact logged source was tested separately; '
                           'container export failed and whole proposer-workspace integrity is not established. '
                           'No model task resolution, official grading or performance promotion.'}))
    except Exception as error:
        atomic_write(root / 'failure.json', canonical({'error': str(error), 'model_calls': 0}))
        raise
    finally:
        atomic_write(root / 'archive-lock.json', canonical({'files': seal(root)}))


if __name__ == '__main__':
    main()
