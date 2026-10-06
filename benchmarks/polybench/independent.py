"""Blind public-test authoring before implementation, with immutable replay."""
import hashlib
from pathlib import Path

from benchmarks.polybench.delivery import is_test_path, production_patch
from benchmarks.polybench.engine import PolyEngine, VisibleVerifier
from benchmarks.polybench.prepare import write
from benchmarks.polybench.public_checks import public_test_contract, public_test_execution
from benchmarks.polybench.regression import regression_check, test_projection
from hx.engine import Engine
from hx.git import assert_clean, derive, git, validate_candidate
from hx.models import Candidate, Check, GateError, Verification, WorkerSummary

VERSION = 'blind-public-challenge@4'


def prepare_independent_replay(candidate, challenge, task, directory, clone_workspace):
    """Original tests plus delivered production plus the immutable challenge."""
    collisions = set(challenge.changed_files) & set(candidate.changed_files)
    if collisions:
        raise GateError('Independent test collision: ' + ', '.join(sorted(collisions)))
    workspace = clone_workspace(Path(candidate.workspace), directory/'workspace', task.base_commit)
    delivered, projection = production_patch(candidate)
    if not delivered.strip():
        raise GateError('Independent replay requires a nonempty production implementation')
    import subprocess
    subprocess.run(['git','-C',str(workspace),'apply','--binary','-'], input=delivered.encode(),
                   check=True,capture_output=True,timeout=30)
    production = derive(workspace,task.base_commit,task.base_commit,task)
    if set(production.changed_files) != set(projection['included_paths']):
        raise GateError('Independent replay source differs from delivered patch')
    patch, paths = test_projection(challenge)
    if any((workspace/path).exists() for path in paths):
        raise GateError('Independent tests overlap original repository')
    subprocess.run(['git','-C',str(workspace),'apply','--binary','-'], input=patch,
                   check=True,capture_output=True,timeout=30)
    overlay = derive(workspace,task.base_commit,production.candidate_commit,task)
    write(directory/'independent-delivery.json', {
        'version':VERSION, 'original_base':task.base_commit,
        'implementation_candidate':candidate.candidate_commit,
        'production_replay_commit':production.candidate_commit,
        'overlay_commit':overlay.candidate_commit, 'delivery':projection,
        'challenge_patch_sha256':hashlib.sha256(patch).hexdigest(),
        'challenge_paths':paths, 'implementer_test_edits_inherited':False})
    return overlay.model_copy(update={'verification_commands':challenge.verification_commands})


def validate_challenge(candidate, task):
    validate_candidate(candidate, task)
    if not candidate.changed_files or not candidate.verification_commands:
        raise GateError('Independent challenge needs new executable tests')
    if len(candidate.verification_commands) > 2:
        raise GateError('Independent challenge exceeds two commands')
    for index, argv in enumerate(candidate.verification_commands, 1):
        try:
            public_test_execution(argv, Path(candidate.workspace))
        except ValueError as error:
            raise GateError(f'Independent challenge command {index} is incompatible: {error}') from error
    if len(candidate.changed_files) > 5 or len(test_projection(candidate)[0]) > 24000:
        raise GateError('Independent challenge exceeds five test files or 24000 patch bytes')
    for path in candidate.changed_files:
        if not is_test_path(path):
            raise GateError('Independent author may change only conventional test files')
        if git(Path(candidate.workspace), 'ls-tree', candidate.base_commit, '--', path):
            raise GateError('Independent author must add new tests, not modify existing tests')


class IndependentEngine(PolyEngine):
    """Same Sol model, separate fresh calls; no patch in test-author context."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.challenge = None
        self.config['independent_challenge'] = VERSION
        from hx.config import digest
        self.config['fingerprint'] = digest({k:v for k,v in self.config.items() if k!='fingerprint'})

    def _worker(self, run_id, step_id, role, task, workspace, context, contract, directory, deadline):
        if step_id == 'independent_challenge':
            self.adapter.workflow_deadline = deadline
            context = {'input_commit': task.base_commit, 'stage': VERSION,
                'public_test_runner_contract': public_test_contract(),
                'instruction': (
                    'You are the independent public regression author. No solution exists yet. '
                    'Inspect only this original repository and public issue. DO NOT implement the fix. '
                    'Add at most five NEW conventional test files, with a combined diff under 24000 bytes; do not change/delete existing source, tests, '
                    'configuration or package manifests. Use existing installed test tooling. '
                    'Write focused functional regressions for the actual reported cause and observable '
                    'behavior, supported input forms/defaults, and important boundary or lifecycle cases. '
                    'Avoid tautologies, mocks that replace the faulty behavior, invented APIs or asserting '
                    'implementation details unrelated to the public contract. Include relevant existing '
                    'compatibility tests in your commands. Return one or two argv-list functional test '
                    'commands with named output (pytest -vv, Mocha --reporter json, Jest --json). '
                    'At least one command must genuinely fail behaviorally on this original code. '
                    'Run the tests and inspect the failure before returning; import/setup errors or empty '
                    'runs do not count. Never commit, alter git history, install dependencies or access '
                    'private acceptance data. Your tests will be frozen and independently replayed against '
                    'the implementer later; they cannot be revised to fit its answer.')}
            return Engine._worker(self, run_id, step_id, role, task, workspace, context,
                                 contract, directory, deadline)
        context = {**context, 'independent_validation': (
            'HX already created separate public regressions on the original source before your fix. '
            'They are withheld initially and replayed unchanged against your patch. Diagnose the '
            'actual cause from the issue and supported source contracts, not just your chosen happy path. '
            'If a replay fails, repair behavior from that public feedback. Green checks alone do not '
            'establish independent benchmark correctness.')}
        return super()._worker(run_id, step_id, role, task, workspace, context,
                              contract, directory, deadline)

    def _prepare_challenge(self, run_id, task, deadline):
        def operation(directory):
            workspace = self._clone(Path(task.repo), directory/'workspace', task.base_commit)
            raw = self._worker(run_id, 'independent_challenge', 'implementer', task, workspace,
                               {}, WorkerSummary, directory, deadline)
            summary = WorkerSummary.model_validate(raw)
            candidate = derive(workspace, task.base_commit, task.base_commit, task)
            candidate = candidate.model_copy(update={'verification_commands': summary.verification_commands})
            validate_challenge(candidate, task)
            return candidate.model_dump()
        challenge = self._step(run_id, 'independent_challenge', {'task':task.model_dump(), 'version':VERSION},
            Candidate, operation, lambda c:validate_challenge(c,task), deadline)
        def reproduce(directory):
            result = regression_check(challenge, task, directory, self.settings, self.verifier.client,
                self.case, lambda:self.check_control(run_id,deadline), self._emit(run_id,'independent_base'))
            return Verification(candidate_commit=challenge.candidate_commit, passed=result.passed,
                checks=[result], changed_line_coverage=None,
                known_gaps=['Blind model-authored tests still require semantic scrutiny.']).model_dump()
        base = self._step(run_id, 'independent_base', {'challenge':challenge.model_dump()},
            Verification, reproduce, lambda _:None, deadline)
        if not base.passed:
            raise GateError('Independent public reproduction not established: '+base.checks[0].evidence)
        patch, _ = test_projection(challenge)
        self.store.event(run_id,'independent_challenge.frozen',data={
            'candidate_commit':challenge.candidate_commit,'test_patch_sha256':hashlib.sha256(patch).hexdigest(),
            'base_behavioral_failure':True,'commands':challenge.verification_commands,
            'implementation_seen':False})
        return challenge

    def _implementation(self, run_id, step_id, task, previous, feedback, deadline):
        if self.challenge is None:
            self.challenge = self._prepare_challenge(run_id,task,deadline)
        if step_id.startswith('revise_'):
            feedback = {**feedback, 'independent_public_tests': {
                'patch':test_projection(self.challenge)[0].decode(),
                'commands':self.challenge.verification_commands,
                'instruction':'These tests are immutable in HX replay. Inspect the failed public assertion; repair production behavior. You may reproduce them locally but cannot replace the stored challenge.'}}
        return super()._implementation(run_id,step_id,task,previous,feedback,deadline)

    def _verify(self, run_id, revision, candidate, task, deadline):
        own = super()._verify(run_id,revision,candidate,task,deadline)
        def operation(directory):
            validate_challenge(self.challenge,task)
            try:
                overlay=prepare_independent_replay(candidate,self.challenge,task,directory,self._clone)
            except GateError as error:
                return Verification(candidate_commit=candidate.candidate_commit,passed=False,
                    checks=[Check(name='independent_delivery',passed=False,evidence=str(error))],
                    changed_line_coverage=None,known_gaps=[]).model_dump()
            # Base reproduction was established before implementation. Here we
            # replay only immutable challenge commands; no coverage claims from
            # the implementer's self-authored mapping enter this verdict.
            result=VisibleVerifier(self.settings,self.verifier.client,self.case).run(overlay,
                task.model_copy(update={'kind':'feature'}),directory/'replay',
                lambda:self.check_control(run_id,deadline),self._emit(run_id,f'independent_verify_{revision}'))
            assert_clean(Path(candidate.workspace),candidate.candidate_commit)
            return result.model_copy(update={'candidate_commit':candidate.candidate_commit}).model_dump()
        independent=self._step(run_id,f'independent_verify_{revision}',
            {'candidate':candidate.model_dump(),'challenge':self.challenge.model_dump(),'version':VERSION},Verification,
            operation,lambda _:None,deadline)
        checks=own.checks+[c.model_copy(update={'name':'independent_'+c.name}) for c in independent.checks]
        return own.model_copy(update={'passed':own.passed and independent.passed,'checks':checks,
            'known_gaps':own.known_gaps+[
                'Public self-checks and blind challenge checks are separate from official correctness. '
                'The same model authors the challenge and fix in separate fresh contexts; shared blind spots remain.']})
