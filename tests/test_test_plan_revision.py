from pathlib import Path

import pytest

from hx.engine import derive_with_test_plan
from hx.git import clone, derive, git, validate_candidate
from hx.models import GateError, HXError, WorkerSummary


def summary(commands):
    return WorkerSummary(summary="Test plan corrected", tests_added=[], limitations=[],
                         verification_commands=commands)


def candidate(project, tmp_path):
    task = project["missing-task"]
    base = git(Path(task.repo), "rev-parse", "HEAD")
    task = task.model_copy(update={"base_commit": base})
    repo = clone(Path(task.repo), tmp_path / "first", base)
    path = repo / "backend/app.py"
    path.write_text(path.read_text() + "\n# A real first candidate change\n")
    result = derive(repo, base, base, task)
    result = result.model_copy(update={"verification_commands": [["git", "diff", "--check"]]})
    return task, result


def test_plan_only_revision_preserves_exact_source_and_diff(project, tmp_path):
    task, previous = candidate(project, tmp_path)
    repo = clone(Path(previous.workspace), tmp_path / "revision", previous.candidate_commit)
    commands = [["pytest", "tests/test_existing.py"]]
    revised = derive_with_test_plan(repo, task, previous.candidate_commit, previous, summary(commands))
    assert revised.candidate_commit == previous.candidate_commit
    assert revised.diff_sha256 == previous.diff_sha256
    assert revised.changed_files == previous.changed_files
    assert revised.verification_commands == commands
    assert git(repo, "rev-parse", "HEAD") == previous.candidate_commit
    validate_candidate(revised, task)


@pytest.mark.parametrize("commands", [[], [["git", "diff", "--check"]]])
def test_unchanged_or_empty_plan_does_not_bypass_no_change_gate(project, tmp_path, commands):
    task, previous = candidate(project, tmp_path)
    repo = clone(Path(previous.workspace), tmp_path / "revision", previous.candidate_commit)
    with pytest.raises(HXError, match="no changes"):
        derive_with_test_plan(repo, task, previous.candidate_commit, previous, summary(commands))


def test_initial_test_plan_without_source_change_still_fails(project, tmp_path):
    task = project["missing-task"]
    base = git(Path(task.repo), "rev-parse", "HEAD")
    task = task.model_copy(update={"base_commit": base})
    repo = clone(Path(task.repo), tmp_path / "initial", base)
    with pytest.raises(HXError, match="no changes"):
        derive_with_test_plan(repo, task, base, None, summary([["pytest", "tests"]]))


def test_plan_change_does_not_mask_history_tampering(project, tmp_path):
    task, previous = candidate(project, tmp_path)
    repo = clone(Path(previous.workspace), tmp_path / "revision", previous.candidate_commit)
    git(repo, "commit", "--allow-empty", "-m", "unauthorized")
    with pytest.raises(GateError, match="different revision"):
        derive_with_test_plan(repo, task, previous.candidate_commit, previous,
                              summary([["pytest", "tests"]]))


def test_real_workflow_reverifies_metadata_only_revision(project, setup_engine):
    from hx.adapters import FakeAdapter
    from hx.models import Check

    class PlanRepairAdapter(FakeAdapter):
        def run(self, role, *args, **kwargs):
            if role == "implementer" and self.calls.get(role, 0):
                self.calls[role] += 1
                return summary([["pytest", "tests"]]).model_dump()
            result = super().run(role, *args, **kwargs)
            if role == "implementer":
                result["verification_commands"] = [["git", "diff", "--check"]]
            return result

    engine, _ = setup_engine()
    engine.settings.max_revisions = 1
    # Re-snapshot settings before creating a run to keep evidence identity honest.
    from hx.config import snapshot
    engine.config = snapshot(engine.settings)
    engine.adapter = PlanRepairAdapter()
    original = engine.verifier

    class PlanVerifier:
        version = "test-plan-gate@1"

        def run(self, candidate, *args):
            result = original.run(candidate, *args)
            valid = candidate.verification_commands == [["pytest", "tests"]]
            result.checks.append(Check(name="public_test_plan", passed=valid,
                                       evidence="Test plan independently checked"))
            result.passed = all(check.passed for check in result.checks)
            return result

    engine.verifier = PlanVerifier()
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    events = engine.store.events(run["id"])
    revised = [e for e in events if e["type"] == "candidate.test_plan_revised"]
    assert len(revised) == 1
    assert revised[0]["data"]["source_changed"] is False
    assert result["handoff"]["revisions_used"] == 1
    assert engine.adapter.calls["implementer"] == 2
    assert any(e["step_id"] == "verify_1" for e in events)
