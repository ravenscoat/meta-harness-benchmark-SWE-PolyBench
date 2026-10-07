"""Explicit user quota amendment at a scored boundary; no scored reruns."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.storage_lifecycle import release_images
from hx.agent_search import SearchPlan, run_search
from hx.code_search import seal, sha
from hx.models import HXError
from scripts import agent_search_polybench as live
from scripts.overnight_limits import account_usage, can_start
from scripts.run_diagnosis_search import PROPOSAL, verify_locks, write
from scripts.run_diagnosis_search_recovery import RecoveryBackend

PARENT = Path('.hx/diagnosis-search-v3')


def quota_allowed(quota, exception):
    if exception:
        return (quota['ordinary_allowed'] and quota['primary']['usedPercent'] < 100
                and quota['secondary']['usedPercent'] < 90)
    return can_start(quota)


class ContinuedBackend(RecoveryBackend):
    def __init__(self, config, root, control, prior):
        super().__init__(config, root, control)
        self.prior = prior
        self.imported = 0
        self.exception_available = True
        self.seeded = True

    def admit(self, plan):
        self.outer_control()
        if self.imported < len(self.prior):
            return  # Read sealed observations only; no image/model admission.
        while True:
            quota = account_usage(runner.BINARY, runner.AUTH)
            write(self.root / 'quota.json', quota)
            if quota_allowed(quota, self.exception_available):
                break
            if self.active:
                raise HXError('Quota exhausted during authorized trial')
            self.outer_control()
            write(self.root / 'phase.json', {'phase': 'natural_quota_wait', 'safe_boundary': True})
            time.sleep(min(30, max(0, plan.deadline - time.time())))
        # Keep all original source/input/settings/provenance/storage checks.
        # This function binding changes only inside this NEW process, under
        # its locked one-trial authorization; no old source bytes are edited.
        original = live.can_start
        live.can_start = lambda q: quota_allowed(q, self.exception_available)
        try:
            return live.PolyBenchBackend.admit(self, plan)
        finally:
            live.can_start = original

    def evaluate(self, source, case, repeat, directory, plan, control):
        if self.imported < len(self.prior):
            prior_folder, row = self.prior[self.imported]
            if (case != row['case'] or repeat != row['repeat']
                    or sha(source.read_bytes()) != row['source_sha256']):
                raise HXError('Sealed carried observation order/source mismatch')
            self.outer_control()
            if self.imported == 0:
                shutil.copytree(PARENT / 'search/development/prior-public-evidence',
                                directory.parents[1] / 'prior-public-evidence')
            for path in prior_folder.iterdir():
                if path.name in {'score.json', 'started.json'}:
                    continue
                destination = directory / path.name
                if path.is_dir():
                    shutil.copytree(path, destination)
                else:
                    shutil.copyfile(path, destination)
            write(directory / 'carried-observation.json', {
                'source': str(prior_folder), 'identity': row['identity'],
                'new_model_calls': 0, 'not_a_fresh_trial': True})
            self.imported += 1
            return row
        try:
            return super().evaluate(source, case, repeat, directory, plan, control)
        finally:
            self.exception_available = False
            write(self.root / 'quota-exception-consumed.json', {
                'case': case, 'repeat': repeat, 'restored_primary_threshold': 80})


def run(root):
    root = root.resolve()
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise HXError('Consumed continuation root cannot restart')
        parent = json.loads((PARENT / 'plan.json').read_text())
        if not (PARENT / 'controller.exited.json').exists():
            raise HXError('Parent must be stopped and sealed first')
        archived = json.loads((PARENT / 'archive-lock.json').read_text())['files']
        if {k: v for k, v in seal(PARENT).items() if k != 'archive-lock.json'} != archived:
            raise HXError('Parent archive changed')
        verify_locks(parent['source_locks'] | parent['historical_scores'])
        prior = []
        for repeat in [1, 2]:
            folder = PARENT / 'search/development/baseline' / f'case-0-repeat-{repeat}'
            row = json.loads((folder / 'score.json').read_text())
            if not row['usage_known'] or row['infrastructure_error'] or row['workflow_error']:
                raise HXError('Only completed known-usage observations can carry forward')
            prior.append((folder, row))
        if len(list((PARENT / 'search').rglob('score.json'))) != 2:
            raise HXError('Expected exactly two completed parent scores')
        if time.time() >= parent['deadline']:
            raise HXError('Original deadline exhausted')
        root.mkdir()
        write(root / 'controller.json', {'pid': os.getpid(), 'started': time.time()})
        parent_prepared = Path(json.loads((PARENT / 'backend-config.json').read_text())['prepared_root'])
        prepared = root / 'prepared'
        prepared.mkdir()
        for name in ['dataset.csv', 'selection.json', 'images.json', 'settings.toml', 'storage.json']:
            shutil.copyfile(parent_prepared / name, prepared / name)
        for name in ['public', 'preflight']:
            shutil.copytree(parent_prepared / name, prepared / name)
        config = json.loads((PARENT / 'backend-config.json').read_text())
        config['prepared_root'] = str(prepared)
        config['private_root'] = str(Path('/opt/hx-polybench-runtime/v1') / root.name)
        config_path = root / 'backend-config.json'
        write(config_path, config)
        locks = parent['source_locks'] | parent['historical_scores'] | {
            str((PARENT / key).resolve()): value for key, value in archived.items()}
        for path in [Path(__file__), config_path, PARENT / 'archive-lock.json',
                     Path('scripts/run_diagnosis_quota_continuation.py'),
                     *[p for p in prepared.rglob('*') if p.is_file()]]:
            locks[str(path.resolve())] = sha(path.read_bytes())
        plan = dict(parent)
        plan.update({'source_locks': locks, 'parent': str(PARENT),
                     'carried_scores': 2, 'carried_reported_tokens': sum(r['reported_tokens'] for _, r in prior),
                     'quota_amendment': 'User explicitly authorizes remaining ordinary primary quota for ONE additional trial; then restore <80%. Weekly<90 and ordinary allowance remain required.',
                     'no_scored_reruns': True})
        write(root / 'plan.json', plan)
        fingerprint = sha((root / 'plan.json').read_bytes())
        write(root / 'plan.lock.json', {'sha256': fingerprint})
        fields = ['development', 'heldout', 'proposals', 'repeats', 'max_reported_tokens',
                  'deadline', 'trial_token_headroom', 'proposal_token_headroom', 'model', 'reasoning_effort']
        search_plan = SearchPlan(**{key: parent[key] for key in fields},
                                source_locks=locks | {str(root / 'plan.json'): fingerprint})
        write(root / 'search-plan.json', search_plan.model_dump())
        def control():
            if time.time() >= parent['deadline']:
                raise HXError('Original deadline exhausted')
            verify_locks(locks | {str(root / 'plan.json'): fingerprint})
            if shutil.disk_usage(Path.cwd()).free < 40 * 1024**3:
                raise HXError('40 GiB host storage guard')
        try:
            backend = ContinuedBackend(config_path, root, control, prior)
            report = run_search(root / 'search', search_plan, PROPOSAL / 'baseline.py', backend)
            write(root / 'final-audit.json', {'report': report, 'carried_not_fresh': 2})
            write(root / 'phase.json', {'phase': 'completed'})
        except BaseException as error:
            write(root / 'stop.json', {'error': str(error), 'retry_allowed': False})
            write(root / 'phase.json', {'phase': 'stopped', 'error': str(error)})
            raise
        finally:
            _, images, client, _ = runner.resources(prepared)
            try:
                write(root / 'release.json', release_images(client, list(images.values())))
            finally:
                client.close()
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})
            write(root / 'archive-lock.json', {'files': seal(root)})


if __name__ == '__main__':
    run(Path(sys.argv[1]))
