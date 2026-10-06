"""Replay public checks on the exact production-only benchmark projection.

This uses public paths and commands only. Existing test expectations may conflict
with an intentional behavior change; a failed check is not proof of task error.
"""
from pathlib import Path

from benchmarks.polybench.containers import archive, command, create, populate
from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.prepare import write
from benchmarks.polybench.public_checks import public_test_execution
from benchmarks.polybench.regression import classify_public_logs
from benchmarks.polybench.report_capture import capture_argv
from benchmarks.polybench.test_environment import docker_environment
from benchmarks.polybench.worker_environment import build_check
from hx.check_execution import command_check
from hx.models import Check
from hx.process import clean_env

VERSION = 'public-delivery-parity@1'


def replay_delivery(candidate, directory, settings, client, case, control, emit):
    patch, projection = production_patch(candidate)
    record = {'version': VERSION, 'projection': projection, 'commands': [],
        'model_calls': 0, 'official_grader_calls': 0,
        'limitation': 'Public original tests may encode superseded expectations. Failure requires diagnosis, not reverting requested behavior or claiming official cause.'}
    container, workdir = create(client, case, offline=True)
    try:
        control()
        populate(container, workdir, Path(candidate.workspace), case)
        command(container, ['git', 'reset', '--hard', candidate.base_commit], workdir, '1000:1000')
        command(container, ['git', 'clean', '-fd'], workdir, '1000:1000')
        if patch:
            if not container.put_archive('/tmp', archive({'hx-delivered.patch': patch.encode()}, uid=1000)):
                raise RuntimeError('Production-only patch transfer failed')
            command(container, ['git', 'apply', '--binary', '/tmp/hx-delivered.patch'], workdir, '1000:1000')
        command(container, ['git', 'add', '--all'], workdir, '1000:1000')
        paths = command(container, ['git', 'diff', '--cached', '--name-only', '-z',
            candidate.base_commit], workdir, '1000:1000').decode().split('\0')
        if set(filter(None, paths)) != set(projection['included_paths']):
            raise RuntimeError('Delivery replay differs from production projection')
        tree = command(container, ['git', 'write-tree'], workdir, '1000:1000')
        build = build_check(container, workdir, Path(case['repo_path']), case,
            directory / 'build', settings, control, emit)
        record['build_passed'] = build.passed if build else None
        if build and not build.passed:
            record['passed'] = False
            return Check(name='public_delivery_parity', passed=False,
                         evidence='Production-only public build failed; see delivery-parity evidence.')
        for index, argv in enumerate(candidate.verification_commands, 1):
            control()
            # Resolve scripts against original public manifests, not edited tests.
            actual, env, adaptations = public_test_execution(argv, Path(case['repo_path']))
            logs = directory / f'test_{index}'
            check = command_check('delivery_test_' + str(index),
                ['docker', 'exec', '-u', '1000:1000', *docker_environment(),
                 *[item for k, v in env.items() for item in ('-e', k + '=' + v)],
                 '-w', workdir, container.id, *capture_argv(actual, settings.max_log_bytes)],
                directory, clean_env(), logs, settings, control, emit)
            category, ingestion = classify_public_logs(check, logs, settings)
            record['commands'].append({'argv': actual, 'adaptations': adaptations,
                'check': check.model_dump(), 'category': category, 'ingestion': ingestion})
        command(container, ['git', 'add', '--all'], workdir, '1000:1000')
        record['tracked_source_unchanged'] = tree == command(container,
            ['git', 'write-tree'], workdir, '1000:1000')
        record['passed'] = (bool(record['commands']) and record['tracked_source_unchanged']
            and all(row['check']['passed'] and row['category'] == 'baseline_passed'
                    for row in record['commands']))
        return Check(name='public_delivery_parity', passed=record['passed'],
            evidence=('Production-only public replay passed.' if record['passed'] else
                'Production-only public replay differs from full-candidate verification. '
                'Inspect original test expectations and delivered source; public green is not delivery validation. '
                'Do not restore obsolete behavior solely to pass original tests. '
                + '\n'.join(row['check']['evidence'][-4000:] for row in record['commands'])))
    finally:
        write(directory / 'delivery-parity.json', record)
        container.remove(force=True)
