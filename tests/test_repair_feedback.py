import sys

import pytest

from hx import check_execution
from hx.adapters import FakeAdapter
from hx.models import Cancelled, GateError, HXError, ProcessTimeout, Settings
from hx.process import clean_env


def test_real_timeout_preserves_diagnostics_and_produces_failed_check(tmp_path):
    events = []
    result = check_execution.command_check(
        "react_tests", [sys.executable, "-u", "-c",
                        "import time; print('last test: overlapping saves', flush=True); time.sleep(30)"],
        tmp_path, clean_env(), tmp_path / "logs",
        Settings(verification_timeout_seconds=1), lambda: None,
        lambda kind, data: events.append((kind, data)),
    )
    assert not result.passed
    assert "last test: overlapping saves" in result.evidence
    assert "Child tree terminated" in result.evidence
    assert [kind for kind, _ in events] == [
        "verification.started", "verification.timeout", "verification.check",
    ]


@pytest.mark.parametrize("error", [Cancelled("cancel"), GateError("integrity"),
                                  HXError("run time budget exhausted"), HXError("log budget")])
def test_global_and_integrity_errors_do_not_become_repair_feedback(tmp_path, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(check_execution, "execute", fail)
    with pytest.raises(type(error), match=str(error)):
        check_execution.command_check("test", [], tmp_path, {}, tmp_path,
                                      Settings(), lambda: None, lambda *_: None)


def test_timeout_rechecks_global_control(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise ProcessTimeout("command timed out")

    def exhausted():
        raise HXError("run time budget exhausted")

    monkeypatch.setattr(check_execution, "execute", timeout)
    with pytest.raises(HXError, match="run time budget"):
        check_execution.command_check("test", [], tmp_path, {}, tmp_path,
                                      Settings(), exhausted, lambda *_: None)


def test_inspection_gap_only_preserves_candidate_without_empty_revision(project, setup_engine):
    class GapOnly(FakeAdapter):
        def run(self, role, *args, **kwargs):
            result = super().run(role, *args, **kwargs)
            if role == "correctness":
                result["could_not_inspect"] = ["external dependency unavailable"]
            return result

    engine, _ = setup_engine()
    engine.adapter = GapOnly()
    # The fixture creates a config with a revision budget of zero by default;
    # recreate the engine so this checks early stopping with revisions available.
    from hx.engine import Engine

    engine = Engine(engine.store, engine.settings.model_copy(update={"max_revisions": 2}), engine.adapter)
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention"
    assert result["handoff"]["revisions_used"] == 0
    assert engine.adapter.calls["implementer"] == 1
    assert any(e["type"] == "revision.skipped" for e in engine.store.events(run["id"]))
    with pytest.raises(GateError, match="missing review evidence"):
        engine.decision(run["id"], result["handoff"]["candidate_commit"], True)


def test_blocker_still_gets_revision_with_exact_source_and_failed_check_evidence(project, setup_engine):
    class Capture(FakeAdapter):
        plans = []

        def run(self, role, task, workspace, context, *args, **kwargs):
            if role == "implementer" and "repair_plan" in context:
                self.plans.append(context["repair_plan"])
            return super().run(role, task, workspace, context, *args, **kwargs)

    from hx.engine import Engine

    engine, _ = setup_engine()
    adapter = Capture("always-blocking")
    engine = Engine(engine.store, engine.settings.model_copy(update={"max_revisions": 1}), adapter)
    original_verify = engine.verifier.run

    def failed_check(*args, **kwargs):
        from hx.models import Check

        result = original_verify(*args, **kwargs)
        result.checks.append(Check(name="transition-test", passed=False,
                                   evidence="new work disappeared during an overlapping save"))
        result.passed = False
        return result

    engine.verifier.run = failed_check
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention", result["error"]
    assert len(adapter.plans) == 1
    assert set(adapter.plans[0]["blocking_sources"]) == {"correctness:f1", "security:f1"}
    assert adapter.plans[0]["candidate_commit"]
    assert adapter.plans[0]["failed_checks"][-1]["evidence"] == "new work disappeared during an overlapping save"
    assert result["handoff"]["candidate_commit"] != adapter.plans[0]["candidate_commit"]
    assert adapter.calls["implementer"] == 2


def test_fullstack_timeout_keeps_build_and_review_evidence(tmp_path, monkeypatch):
    from hx import challenge_eval
    from hx.models import Candidate, Task

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(challenge_eval, "clone", lambda *_: repo)
    monkeypatch.setattr(challenge_eval, "prepare_frontend", lambda *_: None)
    monkeypatch.setattr(challenge_eval, "assert_clean", lambda *_: None)
    calls = []

    def execute(command, cwd, env, logs, *args, **kwargs):
        calls.append(logs.name)
        if logs.name == "react_tests":
            raise ProcessTimeout("process timed out after 1s")
        return 0, "passed", ""

    monkeypatch.setattr(check_execution, "execute", execute)
    candidate = Candidate(base_commit="base", input_commit="base", candidate_commit="head",
                          workspace=str(repo), changed_files=[], diff_sha256="hash")
    task = Task(id="async", repo=str(repo), report="Repair asynchronous state transitions", frontend=True)
    result = challenge_eval.FullstackVerifier(Settings()).run(
        candidate, task, tmp_path, lambda: None, lambda *_: None,
    )
    assert calls == ["backend_tests", "react_tests", "react_build"]
    assert not result.passed
    assert result.checks[1].name == "react_tests" and not result.checks[1].passed
    assert result.checks[2].passed
