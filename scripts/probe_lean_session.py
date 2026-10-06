"""Bounded two-call native history transport smoke; no coding or official grading."""
import json
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench.containers import ContainerAdapter
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.runner import AUTH, BINARY
from benchmarks.polybench.sessions import TaskSessions
from hx.git import assert_clean, clone, git
from hx.models import Settings, Task, WorkerSummary
from hx.usage import usage_breakdown
from scripts.overnight_limits import account_usage, can_start


def probe(root):
    if root.exists():
        raise RuntimeError('New diagnostic identity required')
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        root.mkdir(parents=True)
        original = json.loads(Path('.hx/polybench-v1/images.json').read_text())
        case = original['mui__material-ui-34207']
        work = Path('/opt/hx-polybench-runtime/v1/infra-checks') / root.name / 'workspace'
        source = Path(case['repo_path'])
        head = git(source, 'rev-parse', 'HEAD')
        workspace = clone(source, work, head)
        task = Task(id='native-history-transport-only', repo=str(source), base_commit=head,
                    report='Test session transport only; do not solve or inspect a repository issue.', kind='feature')
        settings = Settings(adapter='fake', workflow='single', worker_model='gpt-6.1-sol',
                            judgment_model='gpt-6.1-sol', attempt_timeout_seconds=120,
                            max_observed_tokens=40000)
        import docker
        adapter = ContainerAdapter(settings, docker.from_env(), case, BINARY, AUTH)
        adapter.sessions = TaskSessions()
        adapter.workflow_deadline = time.monotonic() + 300
        files = [Path('benchmarks/polybench/containers.py'), Path('benchmarks/polybench/sessions.py'),
                 Path('src/hx/usage.py'), Path(__file__)]
        hashes = {str(p): sha(p) for p in files}
        write(root / 'plan.json', {'model': settings.worker_model, 'max_calls': 2,
            'max_reported_tokens': 40000, 'source_hashes': hashes,
            'limitation': 'Native history transport only; no coding score or task-resolution evidence.'})
        events, used, results = [], 0, []
        def emit(name, data):
            nonlocal used
            events.append({'type': name, 'data': data})
            if name == 'worker.usage':
                detail = usage_breakdown(data.get('reported_usage'))
                if not detail['usage_known']:
                    raise RuntimeError('Smoke usage unknown; no further call permitted')
                used += detail['reported_tokens']
            write(root / 'events.json', events)
        def control():
            if time.monotonic() >= adapter.workflow_deadline or used >= 40000:
                raise RuntimeError('Transport smoke envelope exhausted')
        try:
            for index in range(2):
                quota = account_usage(BINARY, AUTH)
                write(root / ('quota-' + str(index) + '.json'), quota)
                if not can_start(quota) or used > 20000:
                    raise RuntimeError('Quota or headroom blocks smoke call')
                control()
                directory = root / ('call-' + str(index))
                directory.mkdir()
                context = {'native_session_scope': root.name,
                    'native_session_continuation': index == 1,
                    'repair_plan': {'instruction': 'Return the marker word remembered from the previous turn as summary. '
                                   'Do not read files, use tools or change source. All list fields must be empty.'}}
                instructions = ('Session transport smoke. Do not inspect files, run commands or change source. '
                                'Return structured output with summary exactly amber-otter, and all list fields empty. '
                                'Remember this marker for the next turn.')
                result = adapter.run('implementer', task, workspace, context, instructions,
                    WorkerSummary, directory, control, emit, 120)
                results.append(result)
                assert result['summary'] == 'amber-otter', 'Resumed session did not preserve marker'
                assert_clean(workspace, head)
            assert [e['data']['resumed'] for e in events if e['type'] == 'worker.session'] == [False, True]
            assert all(sha(Path(p)) == h for p, h in hashes.items())
            write(root / 'audit.json', {'passed': True, 'calls': 2, 'results': results,
                'reported_tokens': used, 'source_unchanged': True, 'official_calls': 0,
                'benchmark_trials': 0, 'session_resumed': True,
                'limitation': 'Transport works; no task-level cost or solve-rate improvement established.'})
        except Exception as error:
            write(root / 'failure.json', {'error': str(error), 'reported_tokens': used,
                'results': results, 'accepted': False, 'benchmark_trials': 0, 'official_calls': 0})
            raise


if __name__ == '__main__':
    import sys
    probe(Path(sys.argv[1]))
