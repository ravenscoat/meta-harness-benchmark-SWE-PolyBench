"""Opt-in single solver; existing independent-author engines are unchanged."""
import hashlib
import subprocess
from pathlib import Path

from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.engine import PolyEngine
from benchmarks.polybench.prepare import write
from benchmarks.polybench.regression import test_projection
from benchmarks.polybench.sessions import VERSION, TaskSessions
from hx.config import digest
from hx.git import assert_clean, derive, git, validate_candidate
from hx.models import Check, GateError, Verification

PUBLIC_REPLAY_CONTRACT = (
    'Independent replay preserves original tests and excludes edits to existing test files. '
    'Add requested-behavior regressions in NEW conventional test files; do not alter '
    'original tests, fixtures or configuration to obtain a passing result. '
    'Choose bounded functional commands that execute those new files and report named '
    'test outcomes (for example pytest -vv or a supported Mocha/Jest JSON reporter). '
    'The regression must demonstrate the requested behavior failing on original source '
    'and passing on the delivered production patch. Test discovery alone is not evidence.'
)


def prepare_lean_replay(candidate, task, directory, clone_workspace):
    validate_candidate(candidate, task)
    workspace = clone_workspace(Path(candidate.workspace), directory / 'workspace', task.base_commit)
    delivered, projection = production_patch(candidate)
    if not delivered.strip():
        raise GateError('Lean verification requires nonempty production delivery')
    subprocess.run(['git', '-C', str(workspace), 'apply', '--binary', '-'],
                   input=delivered.encode(), check=True, capture_output=True, timeout=30)
    production = derive(workspace, task.base_commit, task.base_commit, task)
    if set(production.changed_files) != set(projection['included_paths']):
        raise GateError('Lean source differs from production delivery')
    _, paths = test_projection(candidate)  # validates regular public test paths/size
    added = [p for p in paths if not git(Path(candidate.workspace), 'ls-tree', task.base_commit, '--', p)
             and (Path(candidate.workspace) / p).is_file()]
    tests = b''
    if added:
        tests = subprocess.check_output(['git', '-C', candidate.workspace, 'diff', '--binary',
            '--no-ext-diff', '--no-textconv', '--no-renames', task.base_commit,
            candidate.candidate_commit, '--', *[':(literal)' + p for p in added]], timeout=30)
        subprocess.run(['git', '-C', str(workspace), 'apply', '--binary', '-'],
                       input=tests, check=True, capture_output=True, timeout=30)
        overlay = derive(workspace, task.base_commit, production.candidate_commit, task)
    else:
        overlay = production
    write(directory / 'lean-delivery.json', {'production': projection,
        'new_public_test_paths': added, 'existing_test_edits_inherited': False,
        'public_test_patch_sha256': hashlib.sha256(tests).hexdigest(),
        'original_base': task.base_commit, 'production_commit': production.candidate_commit,
        'replay_commit': overlay.candidate_commit,
        'limitation': 'New tests are authored by the solver; there is no blind test author.'})
    return overlay.model_copy(update={'verification_commands': candidate.verification_commands,
                                      'public_contract': candidate.public_contract})


class LeanEngine(PolyEngine):
    def __init__(self, *args, **kwargs):
        if kwargs.get('worker_scaffold') is not None:
            raise ValueError('Lean engine uses native Codex loop, not an outer scaffold')
        super().__init__(*args, **kwargs)
        if self.settings.workflow != 'single' or self.settings.max_revisions > 1:
            raise ValueError('Lean engine requires single workflow and at most one repair')
        self.adapter.sessions = TaskSessions()
        self.config['lean_execution'] = {
            'version': VERSION, 'blind_author': False, 'native_history': True,
            'public_replay_contract': PUBLIC_REPLAY_CONTRACT,
            'independent_public_replay': 'original base + exact production delivery + new public tests',
            'limitation': 'No blind model-authored challenge; public tests do not establish official resolution.',
        }
        self.config['fingerprint'] = digest({k: v for k, v in self.config.items() if k != 'fingerprint'})

    def _worker(self, run_id, step_id, role, task, workspace, context, contract, directory, deadline):
        # Namespaced explicitly by run; no author/reviewer shares this history.
        context = {**context, 'native_session_scope': run_id}
        if not step_id.startswith('revise_'):
            context['public_replay_contract'] = PUBLIC_REPLAY_CONTRACT
        if step_id.startswith('revise_'):
            # Native history already contains issue, source inspection and prior work.
            context['native_session_continuation'] = True
        return super()._worker(run_id, step_id, role, task, workspace, context,
                               contract, directory, deadline)

    def _verify(self, run_id, revision, candidate, task, deadline):
        step_id = f'verify_{revision}'
        def operation(directory):
            try:
                replay = prepare_lean_replay(candidate, task, directory, self._clone)
            except GateError as error:
                return Verification(candidate_commit=candidate.candidate_commit, passed=False,
                    checks=[Check(name='lean_delivery', passed=False, evidence=str(error))],
                    changed_line_coverage=None, known_gaps=[]).model_dump()
            result = self.verifier.run(replay, task, directory / 'replay',
                lambda: self.check_control(run_id, deadline), self._emit(run_id, step_id))
            assert_clean(Path(candidate.workspace), candidate.candidate_commit)
            return result.model_copy(update={'candidate_commit': candidate.candidate_commit,
                'known_gaps': result.known_gaps + [
                    'No blind test author. Original public tests and new solver tests replay '
                    'on the exact production delivery; official resolution remains separate.']}).model_dump()
        def validate(result):
            if (result.candidate_commit != candidate.candidate_commit or not result.checks
                    or result.passed != all(c.passed for c in result.checks)):
                raise GateError('Inconsistent lean verification receipt')
            validate_candidate(candidate, task)
        return self._step(run_id, step_id, {'candidate': candidate.model_dump(),
            'task': task.model_dump(), 'lean_version': VERSION}, Verification,
            operation, validate, deadline)
