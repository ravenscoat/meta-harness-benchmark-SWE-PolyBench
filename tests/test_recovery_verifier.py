import pytest

from benchmarks.advanced import runner
from hx.models import Cancelled, Candidate, HXError, Settings, Task


def test_test_timeout_becomes_failed_check_and_remaining_checks_run(tmp_path, monkeypatch):
    repo = tmp_path / "workspace"
    repo.mkdir()
    (tmp_path / "verification").mkdir()
    (repo / "frontend").mkdir()
    monkeypatch.setattr(runner, "clone", lambda *_: repo)
    monkeypatch.setattr(runner, "prepare_frontend", lambda *_: None)
    monkeypatch.setattr(runner, "assert_clean", lambda *_: None)
    calls = []

    def execute(*args, **kwargs):
        calls.append(args[3].name)
        if args[3].name == "react_tests":
            raise HXError("process timed out after 1s")
        return 0, "passed", ""

    monkeypatch.setattr(runner, "execute", execute)
    candidate = Candidate(
        base_commit="base",
        input_commit="base",
        candidate_commit="candidate",
        changed_files=[],
        workspace=str(repo),
        diff_sha256="hash",
    )
    task = Task(id="repair", repo=str(repo), report="Repair an asynchronous React test")
    result = runner.RecoveryVerifier(Settings()).run(
        candidate, task, tmp_path / "verification", lambda: None, lambda *_: None
    )
    assert not result.passed
    assert calls == ["backend_tests", "react_tests", "react_build"]
    assert result.checks[1].passed is False
    assert "timed out" in result.checks[1].evidence


def test_cancellation_is_not_downgraded_to_repair_feedback(tmp_path, monkeypatch):
    repo = tmp_path / "workspace"
    repo.mkdir()
    (tmp_path / "verification").mkdir()
    monkeypatch.setattr(runner, "clone", lambda *_: repo)
    monkeypatch.setattr(runner, "prepare_frontend", lambda *_: None)

    def cancelled(*args, **kwargs):
        raise Cancelled("human cancelled")

    monkeypatch.setattr(runner, "execute", cancelled)
    candidate = Candidate(
        base_commit="base",
        input_commit="base",
        candidate_commit="candidate",
        changed_files=[],
        workspace=str(repo),
        diff_sha256="hash",
    )
    task = Task(id="repair", repo=str(repo), report="Repair an asynchronous React test")
    with pytest.raises(Cancelled):
        runner.RecoveryVerifier(Settings()).run(
            candidate, task, tmp_path / "verification", lambda: None, lambda *_: None
        )


def test_private_acceptance_timeout_scores_failure_without_aborting_campaign(monkeypatch):
    def timeout(*args, **kwargs):
        raise HXError("process timed out after 1s")

    monkeypatch.setattr(runner, "execute", timeout)
    code, _, diagnostic = runner.acceptance_command()
    assert code == 1
    assert "timed out" in diagnostic
