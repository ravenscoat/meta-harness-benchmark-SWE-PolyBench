"""New zero-model recovery root; original search deadline/ceiling and policies."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.image_transport import ensure_pinned
from benchmarks.polybench.storage_lifecycle import release_images
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.agent_search import SearchPlan, run_search
from hx.code_search import seal, sha
from hx.models import HXError
from scripts.run_diagnosis_search import (
    CASES,
    PROPOSAL,
    DiagnosedBackend,
    prepare,
    verify_locks,
    write,
)

PARENT = Path('.hx/diagnosis-search-v2')
COMPLETION = Path('.hx/diagnosis-search-completion-v2')


def stopped_zero_model_parent(parent=PARENT, completion=COMPLETION, native=None):
    completed = json.loads((completion / 'archive-lock.json').read_text())['files']
    if {k: v for k, v in seal(completion).items() if k != 'archive-lock.json'} != completed:
        raise HXError('Preserved completion audit changed')
    expected = json.loads((parent / 'archive-lock.json').read_text())['files']
    if {k: v for k, v in seal(parent).items() if k != 'archive-lock.json'} != expected:
        raise HXError('Preserved parent archive changed')
    audit = json.loads((completion / 'final-audit.json').read_text())
    if (audit['coding_model_calls'] != 0 or audit['proposer_calls'] != 0
            or audit['official_grader_calls'] != 0 or audit['fresh_coding_scores'] != 0):
        raise HXError('Only an audited zero-model preparation can recover')
    if not (parent / 'controller.exited.json').exists():
        raise HXError('Parent controller has not exited')
    native = native or Path('/opt/hx-polybench-runtime/v1') / parent.name
    if any(native.glob('trial-*')) or any(native.glob('hx-agent-proposer-*')):
        raise HXError('Parent has a consumed native model identity')
    plan = json.loads((parent / 'plan.json').read_text())
    verify_locks(plan['source_locks'] | plan['historical_scores'])
    return plan


class RecoveryBackend(DiagnosedBackend):
    def __init__(self, config, root, control):
        super().__init__(config, root, control)
        self.fresh_worker_images = set()

    def retain(self, case):
        self.outer_control()
        _, images, client, settings = runner.resources(self.prepared)
        try:
            release = release_images(client, [pin for key, pin in images.items() if key != case])
            if any(row['status'] == 'kept' for row in release):
                raise HXError('One-image guard blocked; preserve unrelated references')
            write(self.root / 'phase.json', {'phase': 'pinned_image_transfer', 'case': case})
            ensure_pinned(client, self.prepared, images[case], self.outer_control)
            # Copied all-task receipts stay authoritative; freshly check each actual
            # retained image before using it in a model workspace.
            if case not in self.fresh_worker_images:
                directory = self.root / 'fresh-worker-preflight' / case
                receipt = worker_environment_check(client, images[case], Path(images[case]['repo_path']),
                                                   directory, settings, self.outer_control,
                                                   lambda *args: None)
                if not receipt.get('passed'):
                    raise HXError('Fresh worker gate failed: ' + case)
                self.fresh_worker_images.add(case)
            write(self.root / 'retention.json', {'case': case, 'image_id': images[case]['image_id'],
                                               'others_released': release})
        finally:
            client.close()

    def release(self, case, directory):
        # Keep just this case through consecutive repeats. retain() releases it
        # at the next case switch; the controller releases everything on exit.
        write(directory / 'retention-boundary.json', {'case': case, 'status': 'retained',
              'reason': 'One recorded image reused for consecutive same-case trials; release on switch or exit'})


def run(root):
    root = root.resolve()
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise HXError('Consumed recovery root cannot restart')
        inherited = stopped_zero_model_parent()
        if time.time() >= inherited['deadline']:
            raise HXError('Inherited original deadline exhausted; no late start')
        root.mkdir()
        write(root / 'controller.json', {'pid': os.getpid(), 'started': time.time()})
        prepared, images = None, {}
        try:
            private = Path('/opt/hx-polybench-runtime/v1') / root.name
            prepared, images, inputs, gates = prepare(root, private)
            # Readiness receipts are genuine, sealed and input-compatible. Do not
            # redownload all four solely to reproduce an unchanged gate.
            for case in CASES:
                path = PARENT / 'preparation' / case / 'worker-receipt.json'
                receipt = json.loads(path.read_text())
                if (receipt['case'] != case or receipt['image_id'] != images[case]['image_id']
                        or not receipt['passed'] or not receipt['offline']
                        or receipt['worker_uid'] != 1000 or not receipt['source_clean']):
                    raise HXError('Sealed actual worker receipt does not match original pin')
                destination = root / 'preparation' / case
                destination.mkdir(parents=True)
                shutil.copyfile(path, destination / 'worker-receipt.json')
                inputs[str(path.resolve())] = sha(path.read_bytes())
                gates[case]['worker_gate'] = 'passed_in_preserved_v2'
                gates[case]['actual_receipt_source'] = str(path)
            write(root / 'preparation.json', gates)
            config = root / 'backend-config.json'
            write(config, {'prepared_root': str(prepared), 'private_root': str(private),
                  'prior_public_evidence': str((PROPOSAL / 'prior-public-evidence').resolve()),
                  'carrier_case': CASES[0], 'proposal_seconds': 600,
                  'case_provenance': {case: {'reference_informed': False,
                                    'previous_coding_exposure': case in CASES[:2]} for case in CASES}})
            old_locks = {str((PARENT / name).resolve()): value for name, value in
                         json.loads((PARENT / 'archive-lock.json').read_text())['files'].items()}
            paths = [Path(__file__), Path('scripts/run_diagnosis_search.py'), config,
                     PARENT / 'archive-lock.json', COMPLETION / 'final-audit.json',
                     COMPLETION / 'usage-report.json', COMPLETION / 'archive-lock.json',
                     Path('scripts/agent_search_polybench.py'), Path('scripts/overnight_limits.py'),
                     Path('scripts/run_agent_search.py'), Path('scripts/worker_scaffold_search.py'),
                     *Path('src/hx').glob('*.py'), *Path('src/hx/prompts').glob('*.md'),
                     *Path('src/hx/scaffolds').glob('*.py'), *Path('benchmarks/polybench').glob('*.py'),
                     *(runner.VENDOR / 'src').rglob('*.py'), runner.BINARY,
                     *[p for p in prepared.rglob('*') if p.is_file()],
                     *[p for p in (root / 'preparation').rglob('*') if p.is_file()],
                     *[p for p in PROPOSAL.rglob('*') if p.is_file()]]
            locks = inputs | old_locks | {str(p.resolve()): sha(p.read_bytes()) for p in paths}
            history = inherited['historical_scores']
            plan = {k: inherited[k] for k in ['started', 'deadline', 'max_reported_tokens',
                   'development', 'heldout', 'proposals', 'repeats', 'model', 'reasoning_effort',
                   'trial_token_headroom', 'proposal_token_headroom']}
            plan.update({'source_locks': locks, 'historical_scores': history,
                  'parent_zero_model_recovery': str(PARENT), 'prior_reported_tokens': 0,
                  'planned_development_trials': 8, 'conditional_reserved_trials': 8,
                  'authorization': 'User do it man after registry probe; new stopped-boundary recovery, no old-root resume',
                  'image_policy': 'One image across consecutive case trials; bounded three transport-only retries, no coding retries',
                  'worker_policy': 'Sealed identical four actual gate receipts plus fresh retained-image worker check before first model use',
                  'no_automatic_install': True, 'turn_boundary_overshoot_possible': True})
            write(root / 'plan.json', plan)
            fingerprint = sha((root / 'plan.json').read_bytes())
            write(root / 'plan.lock.json', {'sha256': fingerprint})
            def control():
                if time.time() >= plan['deadline']:
                    raise HXError('Inherited original deadline exhausted; no extension')
                verify_locks(locks | history)
                if sha((root / 'plan.json').read_bytes()) != fingerprint:
                    raise HXError('Recovery plan changed')
                if shutil.disk_usage(Path.cwd()).free < 40 * 1024**3:
                    raise HXError('40 GiB host storage guard')
            fields = ['development', 'heldout', 'proposals', 'repeats', 'max_reported_tokens',
                      'deadline', 'trial_token_headroom', 'proposal_token_headroom', 'model', 'reasoning_effort']
            search_plan = SearchPlan(**{k: plan[k] for k in fields},
                                    source_locks=locks | history | {str(root / 'plan.json'): fingerprint})
            write(root / 'search-plan.json', search_plan.model_dump())
            backend = RecoveryBackend(config, root, control)
            backend.check_program(PROPOSAL / 'baseline.py')
            write(root / 'phase.json', {'phase': 'new_recovery_search', 'models': 0})
            report = run_search(root / 'search', search_plan, PROPOSAL / 'baseline.py', backend)
            control()
            write(root / 'final-audit.json', {'complete': True, 'report': report,
                  'history_verified': len(history), 'automatic_install': False,
                  'limitation': 'Tiny consumed-development/readiness-selected sample; no general superiority claim'})
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
