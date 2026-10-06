import json

from hx.models import Settings
from hx.store import Store
from scripts.hx_console import clean, detail, frame, read_runs


def make_run(tmp_path):
    store = Store(tmp_path / "state")
    run = store.create({"id": "queue-fix"}, Settings().model_dump(), "abc")
    store.update(run["id"], status="running")
    return store, run["id"]


def test_parallel_reviewers_and_sol_are_attributed_from_recorded_models(tmp_path):
    store, run_id = make_run(tmp_path)
    for step, model in (("correctness_0", "gpt-6-luna"),
                        ("security_0", "gpt-6-luna"),
                        ("consolidate_0", "gpt-6.1-sol")):
        store.attempt(run_id, step, "key")
        store.event(run_id, "worker.instantiated", step, {"model": model})
    output = frame(store.root)
    assert "Luna / correctness review (gpt-6-luna)" in output
    assert "Luna / security review (gpt-6-luna)" in output
    assert "Sol / consolidation (gpt-6.1-sol)" in output
    assert "Recorded state, not a process heartbeat" in output


def test_monitor_does_not_create_or_modify_state(tmp_path):
    missing = tmp_path / "missing"
    assert read_runs(missing / "state.sqlite3") == []
    assert "Waiting for a run" in frame(missing)
    assert not missing.exists()
    store, run_id = make_run(tmp_path)
    before = store.get(run_id), store.events(run_id), store.steps(run_id)
    frame(store.root)
    assert before == (store.get(run_id), store.events(run_id), store.steps(run_id))


def test_campaign_score_distinct_from_approval_readiness(tmp_path):
    campaign = tmp_path / "campaign"
    store = Store(campaign / "heldout-results" / "full-queue-1" / "state")
    run = store.create({"id": "queue"}, {}, "abc")
    store.update(run["id"], status="ready_for_approval")
    (campaign / "report.json").write_text(json.dumps({
        "rows": [{"run_id": run["id"], "task_success": False}],
        "totals": {}, "winner_selected_on_search": "full",
    }))
    output = frame(tmp_path, campaign)
    assert "ready_for_approval" in output
    assert "Independent task score: FAIL" in output
    assert "No run recorded as active" in output


def test_terminal_controls_are_removed_and_messages_bounded():
    assert clean("\x1b[2J\x00hello\r\nworld") == "hello world"
    assert len(clean("x" * 1000)) == 180


def test_base_failure_display_waits_for_classification():
    text = detail("verification.check", {"name": "base_test_1", "passed": False})
    assert "awaiting reproduction classification" in text
    assert "FAIL" not in text and "PASS" not in text
    assert "reproduction PASS" in detail("verification.regression", {
        "passed": True, "category": "reproduced", "commands": [{"category": "behavioral_failure"}]})
    assert "reproduction BLOCKED" in detail("verification.regression", {
        "passed": False, "category": "not_reproduced", "commands": [{"category": "setup_error"}]})


def test_controller_setup_stage_shows_even_without_model_runs(tmp_path):
    (tmp_path / "phase.json").write_text(json.dumps({"phase": "preflight", "split": "setup",
        "stage": "image_pull", "case": "mrdoob__three.js-24461", "status": "Downloading"}))
    output = frame(tmp_path, tmp_path)
    assert "Controller: preflight/setup | image_pull | mrdoob__three.js-24461" in output
    assert "Docker: Downloading" in output
    assert "Waiting for a run" in output


def test_official_resolution_not_hidden_by_failed_workflow(tmp_path):
    (tmp_path / "report.json").write_text(json.dumps({"rows": [
        {"task_success": False, "official_resolved": True, "status": "failed"}], "totals": {}}))
    assert "Official resolved: 1" in frame(tmp_path, tmp_path)
