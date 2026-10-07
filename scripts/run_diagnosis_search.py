"""One separately authorized, source-frozen public-diagnosis comparison.

Old campaigns remain stopped. New model identities only, no automatic install.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.storage_lifecycle import release_images
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.agent_search import SearchPlan, run_search
from hx.code_search import copy_experience, seal, sha
from hx.config import canonical
from hx.models import HXError
from hx.store import atomic_write
from hx.worker_scaffold import validate_scaffold
from scripts.agent_search_polybench import PolyBenchBackend
from scripts.overnight_limits import account_usage, can_start
from scripts.worker_scaffold_search import exercise_scaffold

PROPOSAL = Path('.hx/diagnosis-search-proposal-v1')
CASES = ['serverless__serverless-7102', 'serverless__serverless-3457',
         'mui__material-ui-20232', 'sveltejs__svelte-3403']


def write(path, value):
    atomic_write(path, canonical(value))


def verify_locks(locks):
    for name, expected in locks.items():
        if sha(Path(name).read_bytes()) != expected:
            raise HXError('Locked source/input/history changed: ' + name)


def portable_archive(archive):
    """Normalize existing Windows receipt separators, without changing any bytes."""
    normalized = {}
    for name, digest in archive.items():
        relative = name.replace('\\', '/')
        parts = relative.split('/')
        if (not relative or relative.startswith('/') or ':' in relative
                or any(part in {'', '.', '..'} for part in parts) or relative in normalized):
            raise HXError('Unsafe or ambiguous sealed archive path')
        normalized[relative] = digest
    return normalized


def public_history():
    parent = Path('.hx/serverless7102-compatibility-repair-v1/plan.json')
    history = dict(json.loads(parent.read_text())['historical_scores'])
    for pattern in ['*/development/*/*/score.json', '*/development/*/case-*-repeat-*/score.json',
                    '*/heldout/*/case-*-repeat-*/score.json']:
        history.update({str(p.resolve()): sha(p.read_bytes()) for p in Path('.hx').glob(pattern)})
    return history


def import_prior_public(archive, source):
    """Named, sealed proposer-only history; never used as new comparison rows."""
    return copy_experience(archive / 'prior-public-evidence',
                           {p.name: p for p in source.iterdir() if p.is_file()})


class DiagnosedBackend(PolyBenchBackend):
    def __init__(self, config, root, outer_control):
        super().__init__(config)
        self.root = root
        self.outer_control = outer_control
        self.active = False
        self.seeded = False
        self.checked_sources = set()

    def admit(self, plan):
        # Only scored boundaries can wait. Never pause an in-flight worker for quota.
        self.outer_control()
        while not self.active:
            quota = account_usage(runner.BINARY, runner.AUTH)
            write(self.root / 'quota.json', quota)
            if can_start(quota):
                break
            self.outer_control()
            write(self.root / 'phase.json', {'phase': 'natural_quota_wait', 'safe_boundary': True})
            time.sleep(min(30, max(0, plan.deadline - time.time())))
        return super().admit(plan)

    def retain(self, case):
        _, images, client, _ = runner.resources(self.prepared)
        try:
            release = release_images(client, [pin for key, pin in images.items() if key != case])
            if any(row['status'] == 'kept' for row in release):
                raise HXError('One-image guard blocked by another recorded image in use or unrelated references')
            runner.ensure_image(client, self.prepared, images[case])
            write(self.root / 'retention.json', {'case': case, 'image_id': images[case]['image_id'],
                                               'other_recorded_images': release})
        finally:
            client.close()

    def release(self, case, directory):
        _, images, client, _ = runner.resources(self.prepared)
        try:
            release = release_images(client, [images[case]])
            write(directory / 'release.json', release)
            if any(row['status'] == 'kept' for row in release):
                raise HXError('Recorded image could not be safely released at scored boundary')
        finally:
            client.close()

    def check_program(self, source):
        signature = sha(source.read_bytes())
        if signature not in self.checked_sources:
            validate_scaffold(source.read_bytes())
            if not exercise_scaffold(source, self.private / ('fixture-' + signature)):
                raise HXError('Scripted reusable-program fixture failed')
            self.checked_sources.add(signature)
            write(self.root / ('fixture-' + signature + '.json'),
                  {'passed': True, 'source_sha256': signature, 'model_calls': 0,
                   'limitation': 'Scripted integration only, not coding performance'})

    def evaluate(self, source, case, repeat, directory, plan, control):
        self.admit(plan)
        if not self.seeded:
            # run_search seals this append after the first real baseline receipt.
            import_prior_public(directory.parents[1], Path(self.config['prior_public_evidence']))
            self.seeded = True
        self.check_program(source)
        self.retain(case)
        write(self.root / 'phase.json', {'phase': 'coding', 'case': case, 'repeat': repeat,
                                        'arm': directory.parent.name})
        self.active = True
        try:
            return super().evaluate(source, case, repeat, directory, plan, control)
        finally:
            self.active = False
            self.release(case, directory)

    def propose(self, archive, directory, plan, control):
        self.admit(plan)
        carrier = self.config['carrier_case']
        self.retain(carrier)
        write(self.root / 'phase.json', {'phase': 'isolated_public_proposal', 'proposals': 1})
        self.active = True
        try:
            return super().propose(archive, directory, plan, control)
        finally:
            self.active = False
            self.release(carrier, directory)


def prepare(root, private):
    draft = json.loads((PROPOSAL / 'proposal.json').read_text())
    if draft['development'] + draft['heldout'] != CASES:
        raise HXError('Fixed case order changed')
    archive = portable_archive(json.loads((PROPOSAL / 'archive-lock.json').read_text()))
    if {name: value for name, value in seal(PROPOSAL).items() if name != 'archive-lock.json'} != archive:
        raise HXError('Sealed proposal archive changed')
    verify_locks({str(PROPOSAL / p): value for p, value in archive.items()})
    prepared = root / 'prepared'
    prepared.mkdir()
    original = Path('.hx/coding-seventeen-v1')
    selection = json.loads((original / 'selection.json').read_text())
    selection['cases'] = [next(c for c in selection['cases'] if c['id'] == case) for case in CASES]
    shutil.copyfile(original / 'dataset.csv', prepared / 'dataset.csv')
    write(prepared / 'selection.json', selection)
    storage = json.loads((original / 'storage.json').read_text())
    storage['execution_root'] = str(private)
    write(prepared / 'storage.json', storage)
    shutil.copyfile(Path('.hx/stopping-policy-pilot-v1/prepared/settings.toml'), prepared / 'settings.toml')
    images, inputs, gates = {}, {}, {}
    (prepared / 'public').mkdir()
    for case in CASES:
        child = original / 'tasks' / case
        if case in CASES[2:]:
            if any(child.glob('experiments/*/*/state/native-state.json')):
                raise HXError('Reserved task has an existing native coding identity: ' + case)
        for name, expected in draft['prepared_input_hashes'][case].items():
            path = child / name
            if sha(path.read_bytes()) != expected:
                raise HXError('Sealed proposal input changed: ' + str(path))
            inputs[str(path.resolve())] = expected
        pin = json.loads((child / 'images.json').read_text())[case]
        # The original public source and immutable image identities remain fixed.
        if subprocess.check_output(['git', '-C', pin['repo_path'], 'rev-parse', 'HEAD'], text=True).strip() != pin['sanitized_base']:
            raise HXError('Original task base changed: ' + case)
        if subprocess.check_output(['git', '-C', pin['repo_path'], 'status', '--porcelain'], text=True):
            raise HXError('Original task source is dirty: ' + case)
        pin['execution_root'] = str(private)
        images[case] = pin
        shutil.copyfile(child / 'public' / (case + '.json'), prepared / 'public' / (case + '.json'))
        parent = child if case == CASES[0] else Path('.hx/stopping-policy-pilot-v1/prepared')
        gate_path = parent / 'preflight' / case / 'validation.json'
        gate = json.loads(gate_path.read_text())
        if (not gate.get('valid') or gate.get('base_resolved') is not False
                or gate.get('reference_resolved') is not True or gate['image_id'] != pin['image_id']
                or gate['dataset_sha256'] != selection['dataset_sha256']):
            raise HXError('Original trusted scorer setup receipt mismatch: ' + case)
        # Copy only the aggregate setup receipt; private reference contents stay outside public inputs.
        directory = prepared / 'preflight' / case
        directory.mkdir(parents=True)
        shutil.copyfile(gate_path, directory / 'validation.json')
        inputs[str(gate_path.resolve())] = sha(gate_path.read_bytes())
        gates[case] = {'cached_trusted_setup': str(gate_path), 'valid': True, 'worker_gate': 'pending'}
    write(prepared / 'images.json', images)
    write(root / 'preparation.json', gates)
    return prepared, images, inputs, gates


def run(root):
    root = root.resolve()
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise HXError('Consumed comparison root cannot restart')
        root.mkdir()
        started = time.time()
        write(root / 'controller.json', {'pid': os.getpid(), 'started': started})
        prepared, images = None, {}
        try:
            original_started = started
            recovery_locks = {}
            recovery = None
            if root.name == 'diagnosis-search-v2':
                parent = Path('.hx/diagnosis-search-v1')
                raw = json.loads((parent / 'archive-lock.json').read_text())['files']
                if {name: value for name, value in seal(parent).items() if name != 'archive-lock.json'} != raw:
                    raise HXError('Stopped preparation archive changed')
                recovery_locks = {str((parent / name).resolve()): value for name, value in raw.items()}
                recovery_locks[str((parent / 'archive-lock.json').resolve())] = sha((parent / 'archive-lock.json').read_bytes())
                verify_locks(recovery_locks)
                if (set(raw) != {'controller.json', 'controller.exited.json', 'phase.json', 'stop.json'}
                        or json.loads((parent / 'stop.json').read_text())['error'] != 'Sealed proposal archive changed'
                        or (Path('/opt/hx-polybench-runtime/v1') / parent.name).exists()):
                    raise HXError('Recovery requires the exact sealed zero-model preparation failure')
                original_started = json.loads((parent / 'controller.json').read_text())['started']
                recovery = {'parent': str(parent), 'models': 0, 'official_calls': 0,
                            'new_root': str(root), 'reason': 'Portable Windows archive import',
                            'inherited_original_deadline': original_started + 28800,
                            'allowance_unchanged': 12000000}
                write(root / 'recovery.json', recovery)
            private = Path('/opt/hx-polybench-runtime/v1') / root.name
            prepared, images, inputs, gates = prepare(root, private)
            history = public_history()
            verify_locks(history)
            for name in history:
                if '/private-evaluation/' in name:
                    continue
                score = json.loads(Path(name).read_text())
                if score.get('case') in CASES[2:] and ('identity' in score or 'accepted_candidate' in score):
                    raise HXError('Reserved coding score already exists; no replacement authorized')
            # Preserve old scorer code identity; changes to the new harness are separately versioned.
            old = json.loads(Path('.hx/serverless7102-compatibility-repair-v1/plan.json').read_text())
            grader_locks = {name: value for name, value in old['source_locks'].items()
                            if '/SWE-PolyBench-' in name or name.endswith('/benchmarks/polybench/grader.py')}
            verify_locks(grader_locks)
            config = root / 'backend-config.json'
            write(config, {'prepared_root': str(prepared), 'private_root': str(private),
                           'prior_public_evidence': str((PROPOSAL / 'prior-public-evidence').resolve()),
                           'carrier_case': CASES[0], 'proposal_seconds': 600,
                           'case_provenance': {c: {'reference_informed': False,
                             'previous_coding_exposure': c in CASES[:2]} for c in CASES}})
            paths = [Path(__file__), config, Path('scripts/agent_search_polybench.py'),
                     Path('scripts/overnight_limits.py'), Path('scripts/run_agent_search.py'),
                     Path('scripts/worker_scaffold_search.py'),
                     *Path('src/hx').glob('*.py'), *Path('src/hx/prompts').glob('*.md'),
                     *Path('src/hx/scaffolds').glob('*.py'), *Path('benchmarks/polybench').glob('*.py'),
                     *(runner.VENDOR / 'src').rglob('*.py'), runner.BINARY,
                     *[p for p in prepared.rglob('*') if p.is_file()],
                     *[p for p in PROPOSAL.rglob('*') if p.is_file()]]
            locks = {**inputs, **recovery_locks, **{str(p.resolve()): sha(p.read_bytes()) for p in paths}}
            plan = {'development': CASES[:2], 'heldout': CASES[2:], 'proposals': 1, 'repeats': 2,
                    'started': original_started, 'actual_controller_started': started,
                    'deadline': original_started + 28800, 'max_reported_tokens': 12000000,
                    'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium',
                    'trial_token_headroom': 750000, 'proposal_token_headroom': 750000,
                    'source_locks': locks, 'historical_scores': history,
                    'planned_development_trials': 8, 'conditional_reserved_trials': 8,
                    'authorization': 'User go fix it after reviewable separate 12M-token / 8-hour comparison request',
                    'classification': 'Consumed-development executable program search with readiness-selected reserved evaluation; no automatic install',
                    'cached_original_reference_receipts': gates,
                    'preparation_recovery': recovery,
                    'turn_boundary_overshoot_possible': True, 'no_old_campaign_resume': True}
            write(root / 'plan.json', plan)
            plan_hash = sha((root / 'plan.json').read_bytes())
            write(root / 'plan.lock.json', {'sha256': plan_hash})

            def outer_control():
                if time.time() >= plan['deadline']:
                    raise HXError('Original new-comparison deadline exhausted; no extension')
                verify_locks({**locks, **history})
                if sha((root / 'plan.json').read_bytes()) != plan_hash:
                    raise HXError('Campaign plan changed')
                if shutil.disk_usage(Path.cwd()).free < 40 * 1024**3:
                    raise HXError('40 GiB host storage guard')

            # All four real worker gates precede any proposal or coding trial.
            _, _, client, settings = runner.resources(prepared)
            try:
                for case in CASES:
                    outer_control()
                    write(root / 'phase.json', {'phase': 'all_task_offline_worker_preflight', 'case': case})
                    directory = root / 'preparation' / case
                    directory.mkdir(parents=True)
                    try:
                        runner.ensure_image(client, prepared, images[case])
                        receipt = worker_environment_check(client, images[case], Path(images[case]['repo_path']),
                                                           directory / 'worker-preflight', settings,
                                                           outer_control, lambda *args: None)
                        if not receipt.get('passed'):
                            raise HXError('Actual worker gate failed: ' + case)
                        write(directory / 'worker-receipt.json', receipt)
                        gates[case]['worker_gate'] = 'passed'
                        write(root / 'preparation.json', gates)
                    finally:
                        release = release_images(client, [images[case]])
                        write(directory / 'release.json', release)
                        if any(row['status'] == 'kept' for row in release):
                            raise HXError('Preparation image could not be safely released; preserve unrelated references')
            finally:
                client.close()
            frozen_receipts = {str(p.resolve()): sha(p.read_bytes()) for p in
                               (root / 'preparation').glob('*/worker-receipt.json')}
            locks.update(frozen_receipts)
            search_fields = ['development', 'heldout', 'proposals', 'repeats', 'max_reported_tokens',
                             'deadline', 'trial_token_headroom', 'proposal_token_headroom',
                             'model', 'reasoning_effort']
            search_plan = SearchPlan(**{k: plan[k] for k in search_fields},
                                     source_locks={**locks, **history, str(root / 'plan.json'): plan_hash})
            write(root / 'search-plan.json', search_plan.model_dump())
            backend = DiagnosedBackend(config, root, outer_control)
            backend.check_program(PROPOSAL / 'baseline.py')
            report = run_search(root / 'search', search_plan, PROPOSAL / 'baseline.py', backend)
            outer_control()
            write(root / 'final-audit.json', {'complete': True, 'report': report,
                  'historical_scores_verified': len(history), 'source_input_seals_verified': len(locks),
                  'official_outcomes_separate_from_public_readiness': True, 'automatic_install': False,
                  'limitation': 'Small consumed development/readiness-selected reserved sample; no general gain claim'})
            write(root / 'phase.json', {'phase': 'completed', 'winner': report['winner']})
        except BaseException as error:
            write(root / 'stop.json', {'error': str(error), 'retry_allowed': False,
                                      'unreturned_usage_may_be_unknown': True})
            write(root / 'phase.json', {'phase': 'stopped', 'error': str(error)})
            raise
        finally:
            if prepared is not None and images:
                _, _, client, _ = runner.resources(prepared)
                try:
                    write(root / 'release.json', release_images(client, list(images.values())))
                finally:
                    client.close()
            write(root / 'controller.exited.json', {'pid': os.getpid(), 'time': time.time()})
            write(root / 'archive-lock.json', {'files': seal(root)})


if __name__ == '__main__':
    run(Path(sys.argv[1]))
