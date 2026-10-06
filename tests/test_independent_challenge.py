from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.polybench.independent import IndependentEngine, validate_challenge
from hx.engine import Engine
from hx.git import clone, derive, git
from hx.models import Check, GateError, Task, Verification


@pytest.fixture
def repo(tmp_path):
    tmp_path=tmp_path/'repository'
    tmp_path.mkdir()
    git(tmp_path,'init')
    git(tmp_path,'config','user.name','HX test')
    git(tmp_path,'config','user.email','hx@test')
    (tmp_path/'source.py').write_text('value = 0\n')
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests/existing.py').write_text('old = True\n')
    git(tmp_path,'add','--all')
    git(tmp_path,'commit','-m','base')
    return tmp_path


def candidate(repo,path):
    base=git(repo,'rev-parse','HEAD')
    task=Task(id='independent-test',repo=str(repo),report='Fix the incorrect value',base_commit=base,
              allowed_paths=['**'],protected_paths=['__private/**'])
    (repo/path).write_text('assert value == 1\n')
    value=derive(repo,base,base,task).model_copy(update={'verification_commands':[['pytest','-vv','tests']]})
    return value,task


def test_new_test_only_challenge_is_accepted(repo):
    value,task=candidate(repo,'tests/test_challenge.py')
    validate_challenge(value,task)


@pytest.mark.parametrize('path',['source.py','tests/existing.py'])
def test_production_or_existing_test_mutation_is_rejected(repo,path):
    value,task=candidate(repo,path)
    with pytest.raises(GateError):
        validate_challenge(value,task)


def test_empty_or_unbounded_commands_are_rejected(repo):
    value,task=candidate(repo,'tests/test_challenge.py')
    for commands in ([],[['pytest']]*3):
        with pytest.raises(GateError):
            validate_challenge(value.model_copy(update={'verification_commands':commands}),task)


def test_incompatible_author_command_is_rejected_before_base_execution(repo):
    value,task=candidate(repo,'tests/test_challenge.py')
    value=value.model_copy(update={'verification_commands':[['node','arbitrary.js']]})
    with pytest.raises(GateError,match='command 1 is incompatible'):
        validate_challenge(value,task)


def test_blind_author_does_not_receive_patch_or_feedback(monkeypatch,tmp_path):
    engine=IndependentEngine.__new__(IndependentEngine)
    engine.adapter=SimpleNamespace()
    observed={}
    def worker(self,run,step,role,task,workspace,context,*args):
        observed.update(context)
        return {}
    monkeypatch.setattr(Engine,'_worker',worker)
    task=Task(id='blind-test',repo=str(tmp_path),report='Public issue',base_commit='a'*40)
    engine._worker('r','independent_challenge','implementer',task,Path(tmp_path),
                   {'candidate_patch':'PRIVATE_ANSWER','repair_plan':'LEAK'},object,tmp_path,10)
    assert 'PRIVATE_ANSWER' not in str(observed) and 'LEAK' not in str(observed)
    assert observed['input_commit']==task.base_commit
    assert 'No solution exists yet' in observed['instruction']
    assert observed['public_test_runner_contract']['version']=='public-runner-contract@2'


def test_independent_failure_blocks_green_self_checks_with_immutable_overlay(repo,tmp_path,monkeypatch):
    from benchmarks.polybench import independent
    base=git(repo,'rev-parse','HEAD')
    challenge_repo=clone(repo,tmp_path/'blind',base)
    challenge,task=candidate(challenge_repo,'tests/test_challenge.py')
    production,task=candidate(repo,'source.py')
    engine=IndependentEngine.__new__(IndependentEngine)
    engine.challenge=challenge
    engine.settings=SimpleNamespace()
    engine.verifier=SimpleNamespace(client=None)
    engine.case={}
    engine._clone=clone
    engine._emit=lambda *a:lambda *args:None
    engine.check_control=lambda *a:None
    engine._step=lambda run,step,inputs,contract,operation,validate,deadline: contract.model_validate(operation(tmp_path/'verify'))
    monkeypatch.setattr(Engine,'_verify',lambda *a: Verification(
        candidate_commit=production.candidate_commit,passed=True,
        checks=[Check(name='self',passed=True,evidence='green')],changed_line_coverage=None,known_gaps=[]))
    class Replay:
        def __init__(self,*args): pass
        def run(self,overlay,*args):
            assert (Path(overlay.workspace)/'tests/test_challenge.py').read_text()=='assert value == 1\n'
            return Verification(candidate_commit=overlay.candidate_commit,passed=False,
                checks=[Check(name='public_test_1',passed=False,evidence='independent assertion failed')],
                changed_line_coverage=None,known_gaps=[])
    monkeypatch.setattr(independent,'VisibleVerifier',Replay)
    verification=engine._verify('r',0,production,task,100)
    assert not verification.passed
    assert verification.candidate_commit==production.candidate_commit
    assert any(c.name=='independent_public_test_1' and not c.passed for c in verification.checks)
    assert not (repo/'tests/test_challenge.py').exists()
    assert git(repo,'rev-parse','HEAD')==production.candidate_commit


def test_challenge_tampering_is_rejected(repo):
    value,task=candidate(repo,'tests/test_challenge.py')
    (repo/'tests/test_challenge.py').write_text('assert True\n')
    with pytest.raises(GateError):
        validate_challenge(value,task)


def test_independent_replay_excludes_implementer_test_edits(repo,tmp_path,monkeypatch):
    from benchmarks.polybench import independent
    base=git(repo,'rev-parse','HEAD')
    challenge_repo=clone(repo,tmp_path/'blind',base)
    challenge,task=candidate(challenge_repo,'tests/test_challenge.py')
    (repo/'source.py').write_text('value = 1\n')
    (repo/'tests/existing.py').write_text('new = True\n')
    production=derive(repo,base,base,task)
    engine=IndependentEngine.__new__(IndependentEngine)
    engine.challenge=challenge
    engine.settings=SimpleNamespace()
    engine.verifier=SimpleNamespace(client=None)
    engine.case={'repo':'sveltejs/svelte'}
    engine._clone=clone
    engine._emit=lambda *a:lambda *args:None
    engine.check_control=lambda *a:None
    engine._step=lambda run,step,inputs,contract,operation,validate,deadline: contract.model_validate(operation(tmp_path/step))
    def green(commit):
        return Verification(candidate_commit=commit,passed=True,
            checks=[Check(name='self',passed=True,evidence='green')],changed_line_coverage=None,known_gaps=[])
    monkeypatch.setattr(Engine,'_verify',lambda *a:green(production.candidate_commit))
    calls=[]
    class Replay:
        def __init__(self,*args): pass
        def run(self,overlay,*args):
            workspace=Path(overlay.workspace)
            assert (workspace/'tests/existing.py').read_text()=='old = True\n'
            assert (workspace/'source.py').read_text()=='value = 1\n'
            assert (workspace/'tests/test_challenge.py').read_text()=='assert value == 1\n'
            calls.append(overlay.candidate_commit)
            return green(overlay.candidate_commit)
    monkeypatch.setattr(independent,'VisibleVerifier',Replay)
    result=engine._verify('r',0,production,task,100)
    assert len(calls)==1 and calls[0]!=production.candidate_commit
    assert result.passed
    assert (repo/'tests/existing.py').read_text()=='new = True\n'
    assert (tmp_path/'independent_verify_0/independent-delivery.json').exists()


def test_independent_replay_rejects_guessed_challenge_collision(repo,tmp_path):
    from benchmarks.polybench.independent import prepare_independent_replay
    base=git(repo,'rev-parse','HEAD')
    blind=clone(repo,tmp_path/'blind',base)
    challenge,task=candidate(blind,'tests/test_challenge.py')
    production,_=candidate(repo,'source.py')
    collision=production.model_copy(update={'changed_files':production.changed_files+challenge.changed_files})
    with pytest.raises(GateError,match='collision'):
        prepare_independent_replay(collision,challenge,task,tmp_path/'replay',clone)
