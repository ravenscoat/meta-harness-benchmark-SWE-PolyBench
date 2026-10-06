import json
from pathlib import Path

import pytest

from hx.adapters import FakeAdapter
from hx.engine import Engine
from hx.git import git
from hx.models import GateError, HXError


@pytest.mark.parametrize(
    "task_id", ["missing-task", "delete-task", "empty-title", "filter-completed", "rename-task"]
)
def test_full_workflow_exercises_real_app(project, setup_engine, task_id):
    engine, adapter = setup_engine()
    run = engine.create(project[task_id])
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    assert result["handoff"]["verified"] is True
    assert result["handoff"]["reviewed"] is True
    assert result["handoff"]["approval"] == "pending"
    assert result["decision"] is None
    assert adapter.calls == {"implementer": 1, "correctness": 1, "security": 1, "consolidator": 1}
    steps = engine.store.steps(run["id"])
    candidate_step = next(step for step in steps if step["id"] == "implement")
    candidate = engine.store.cached(run["id"], "implement", candidate_step["cache_key"])
    verification_step = next(step for step in steps if step["id"] == "verify_0")
    verification = engine.store.cached(run["id"], "verify_0", verification_step["cache_key"])
    assert verification["changed_line_coverage"] is not None
    assert verification["changed_line_coverage"] > 0
    assert candidate["candidate_commit"] != "invented-123"
    assert git(Path(candidate["workspace"]), "rev-parse", "HEAD") == candidate["candidate_commit"]
    assert git(Path(project[task_id].repo), "rev-parse", "HEAD") == run["base_commit"]
    assert (engine.store.run_dir(run["id"]) / "events.jsonl").exists()


@pytest.mark.parametrize(
    "scenario, message",
    [
        ("malformed", "attempt budget"),
        ("scope-violation", "outside allowed"),
        ("stale-review", "different candidate"),
        ("review-write", "modified"),
        ("drop-blocker", "every source finding"),
    ],
)
def test_failure_is_contained(project, setup_engine, scenario, message):
    engine, _ = setup_engine(scenario)
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "failed"
    assert message in result["error"]
    assert result["handoff"] is None
    assert result["decision"] is None


def test_startup_failure_not_retried(project, setup_engine):
    engine, adapter = setup_engine("startup-failure")
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "failed"
    assert adapter.calls == {"implementer": 1}


def test_healthy_parallel_branch_survives_resume(project, setup_engine):
    engine, adapter = setup_engine("security-fails-once")
    run = engine.create(project["missing-task"])
    first = engine.execute(run["id"])
    assert first["status"] == "failed"
    assert {step["id"]: step["status"] for step in engine.store.steps(run["id"])}[
        "correctness_0"
    ] == "completed"
    second = engine.execute(run["id"], resume=True)
    assert second["status"] == "ready_for_approval", second["error"]
    assert adapter.calls["implementer"] == 1
    assert adapter.calls["correctness"] == 1
    assert adapter.calls["security"] == 2
    replayed = [
        event["step_id"]
        for event in engine.store.events(run["id"])
        if event["type"] == "step.replayed"
    ]
    assert {"implement", "verify_0", "correctness_0"} <= set(replayed)


def test_valid_json_tampering_is_rejected(project, setup_engine):
    engine, _ = setup_engine("security-fails-once")
    run = engine.create(project["missing-task"])
    engine.execute(run["id"])
    path = engine.store.run_dir(run["id"]) / "artifacts" / "correctness_0.json"
    report = json.loads(path.read_text("utf-8"))
    report["could_not_inspect"] = ["tampered"]
    path.write_text(json.dumps(report), "utf-8")
    result = engine.execute(run["id"], resume=True)
    assert result["status"] == "failed"
    assert "integrity" in result["error"]


def test_modified_candidate_is_rejected_on_resume(project, setup_engine):
    engine, _ = setup_engine("security-fails-once")
    run = engine.create(project["missing-task"])
    engine.execute(run["id"])
    step = next(step for step in engine.store.steps(run["id"]) if step["id"] == "implement")
    candidate = engine.store.cached(run["id"], "implement", step["cache_key"])
    (Path(candidate["workspace"]) / "backend" / "app.py").write_text("# altered\n", "utf-8")
    result = engine.execute(run["id"], resume=True)
    assert result["status"] == "failed"
    assert "modified" in result["error"]


def test_configuration_change_cannot_reuse_old_run(project, setup_engine):
    engine, _ = setup_engine("security-fails-once")
    run = engine.create(project["missing-task"])
    engine.execute(run["id"])
    other = Engine(
        engine.store,
        engine.settings.model_copy(update={"worker_model": "changed-model"}),
        FakeAdapter(),
    )
    with pytest.raises(GateError, match="configuration changed"):
        other.execute(run["id"], resume=True)


def test_every_revision_is_reviewed_at_cap(project, setup_engine):
    engine, adapter = setup_engine("always-blocking")
    engine.settings = engine.settings.model_copy(update={"max_revisions": 2})
    # Reconstruct with the actual policy so its fingerprint is truthful.
    engine = Engine(engine.store, engine.settings, adapter)
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention", result["error"]
    assert result["handoff"]["reviewed"] is True
    assert result["handoff"]["revisions_used"] == 2
    assert adapter.calls["implementer"] == 3
    assert adapter.calls["correctness"] == 3
    assert adapter.calls["security"] == 3
    with pytest.raises(GateError, match="blocking findings"):
        engine.decision(run["id"], result["handoff"]["candidate_commit"], True)


def test_broken_revision_cannot_be_approved(project, setup_engine):
    engine, adapter = setup_engine("broken-revision")
    engine = Engine(engine.store, engine.settings.model_copy(update={"max_revisions": 1}), adapter)
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention", result["error"]
    assert result["handoff"]["verified"] is False
    assert result["handoff"]["reviewed"] is True
    step = next(step for step in engine.store.steps(run["id"]) if step["id"] == "verify_1")
    ver = engine.store.cached(run["id"], "verify_1", step["cache_key"])
    assert any(
        check["name"].startswith("compile:") and not check["passed"] for check in ver["checks"]
    )


def test_retry_starts_with_clean_input(project, setup_engine):
    engine, adapter = setup_engine("dirty-retry")
    engine = Engine(engine.store, engine.settings.model_copy(update={"max_attempts": 2}), adapter)
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    step = next(step for step in engine.store.steps(run["id"]) if step["id"] == "implement")
    candidate = engine.store.cached(run["id"], "implement", step["cache_key"])
    assert "backend/partial.py" not in candidate["changed_files"]
    assert (
        engine.store.run_dir(run["id"]) / "steps/implement/attempt-1/workspace/backend/partial.py"
    ).exists()


def test_cancel_before_start_runs_no_worker(project, setup_engine):
    engine, adapter = setup_engine()
    run = engine.create(project["missing-task"])
    engine.store.update(run["id"], cancel_requested=True)
    result = engine.execute(run["id"])
    assert result["status"] == "cancelled"
    assert not adapter.calls


def test_approval_names_exact_commit_and_does_not_merge(project, setup_engine):
    engine, _ = setup_engine()
    task = project["missing-task"]
    run = engine.create(task)
    result = engine.execute(run["id"])
    with pytest.raises(GateError, match="exact handoff commit"):
        engine.decision(run["id"], "0" * 40, True)
    approved = engine.decision(run["id"], result["handoff"]["candidate_commit"], True)
    assert approved["status"] == "approved"
    assert git(Path(task.repo), "rev-parse", "HEAD") == run["base_commit"]
    with pytest.raises(HXError, match="already has"):
        engine.decision(run["id"], result["handoff"]["candidate_commit"], True)


def test_empty_implementation_claim_cannot_advance(project, setup_engine):
    class ClaimOnly(FakeAdapter):
        def run(self, role, *args, **kwargs):
            assert role == "implementer"
            return {"summary": "Done! Commit abc123.", "tests_added": [], "limitations": [],
                    "verification_commands": []}

    engine, _ = setup_engine()
    engine.adapter = ClaimOnly()
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "failed"
    assert "no changes" in result["error"]
    assert not any(step["id"].startswith("verify") for step in engine.store.steps(run["id"]))


def test_incomplete_inspection_is_not_a_clean_review(project, setup_engine):
    class MissingTool(FakeAdapter):
        def run(self, role, *args, **kwargs):
            result = super().run(role, *args, **kwargs)
            if role == "security":
                result["could_not_inspect"] = ["necessary evidence unavailable"]
            return result

    engine, _ = setup_engine()
    engine.adapter = MissingTool()
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention"
    assert "security: necessary evidence unavailable" in result["handoff"]["known_gaps"]
    with pytest.raises(GateError, match="missing review evidence"):
        engine.decision(run["id"], result["handoff"]["candidate_commit"], True)
