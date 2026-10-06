import json

import pytest

from hx.models import HXError
from hx.optimization import BASE_POLICY
from scripts.policy_harness import selected_policy


@pytest.mark.parametrize("targets", [["implementer"], ["implementer", "correctness", "security"]])
def test_adoption_retains_measured_roles_and_rejects_tampering(tmp_path, targets):
    import sqlite3

    from hx.config import digest
    from scripts.policy_harness import measured_policy_targets

    campaign(tmp_path, True)
    config = {"policy": BASE_POLICY.model_dump(), "policy_targets": targets}
    config["fingerprint"] = digest(config)
    database = tmp_path / "search-history" / "tuned-1-one-1" / "state" / "state.sqlite3"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, body TEXT)")
        connection.execute(
            "INSERT INTO runs VALUES (?, ?)", ("r-one", json.dumps({"config": config}))
        )
    report_path = tmp_path / "report.json"
    report = json.loads(report_path.read_text())
    report["rows"].append(
        {
            "split": "search",
            "arm": "tuned-1",
            "case": "one",
            "repeat": 1,
            "run_id": "r-one",
            "fingerprint": config["fingerprint"],
        }
    )
    report_path.write_text(json.dumps(report))
    assert measured_policy_targets(tmp_path) == tuple(targets)
    config["policy_targets"] = ["consolidator"]
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE runs SET body=?", (json.dumps({"config": config}),))
    with pytest.raises(HXError, match="integrity"):
        measured_policy_targets(tmp_path)


def campaign(tmp_path, gain):
    (tmp_path / "complete.json").write_text("{}")
    (tmp_path / "selection.json").write_text(
        json.dumps({"arm": "tuned-1", "policy": BASE_POLICY.model_dump()})
    )
    rows = [
        {"case": "one", "repeat": 1, "split": "heldout", "arm": "full", "task_success": False},
        {"case": "one", "repeat": 1, "split": "heldout", "arm": "tuned-1", "task_success": gain},
    ]
    (tmp_path / "report.json").write_text(
        json.dumps({"winner_selected_on_search": "tuned-1", "rows": rows})
    )


def test_policy_requires_completed_reserved_evaluation(tmp_path):
    with pytest.raises(HXError, match="completed"):
        selected_policy(tmp_path)


def test_search_winner_without_reserved_gain_is_not_adopted(tmp_path):
    campaign(tmp_path, False)
    with pytest.raises(HXError, match="did not improve"):
        selected_policy(tmp_path)
    assert selected_policy(tmp_path, experimental=True) == BASE_POLICY


def test_reserved_gain_allows_operator_use_of_policy(tmp_path):
    campaign(tmp_path, True)
    assert selected_policy(tmp_path) == BASE_POLICY


def test_quota_affected_baseline_cannot_prove_policy_improvement(tmp_path):
    campaign(tmp_path, True)
    path = tmp_path / "report.json"
    report = json.loads(path.read_text())
    report["rows"][0]["error"] = "Codex turn failed: usage limit reached"
    path.write_text(json.dumps(report))
    with pytest.raises(HXError, match="provider quota"):
        selected_policy(tmp_path)
    assert selected_policy(tmp_path, experimental=True) == BASE_POLICY


def test_unresolved_evaluator_audit_blocks_normal_adoption(tmp_path):
    campaign(tmp_path, True)
    (tmp_path / "evaluation-audit.json").write_text(json.dumps({"normal_adoption_blocked": True}))
    with pytest.raises(HXError, match="evaluator audit"):
        selected_policy(tmp_path)
    assert selected_policy(tmp_path, experimental=True) == BASE_POLICY


def test_cleared_audit_needs_complete_untampered_proof(tmp_path):
    import hashlib

    campaign(tmp_path, True)
    metadata = {"normal_adoption_blocked": False, "audit_directory": str(tmp_path / "audit")}
    path = tmp_path / "evaluation-audit.json"
    path.write_text(json.dumps(metadata))
    with pytest.raises(HXError, match="proof"):
        selected_policy(tmp_path)
    directory = tmp_path / "audit"
    directory.mkdir()
    program = directory / "compatible_queue.test.jsx"
    program.write_text("fixture")
    proof = {
        "validated": True,
        "campaign_complete": True,
        "original_report_sha": hashlib.sha256((tmp_path / "report.json").read_bytes()).hexdigest(),
        "program_sha": hashlib.sha256(program.read_bytes()).hexdigest(),
        "original_selected": "tuned-1",
        "corrected_selected": "tuned-1",
        "rows": [],
    }
    certificate = directory / "audit.json"
    certificate.write_text(json.dumps(proof))
    metadata["audit_sha"] = hashlib.sha256(certificate.read_bytes()).hexdigest()
    path.write_text(json.dumps(metadata))
    assert selected_policy(tmp_path) == BASE_POLICY
    certificate.write_text("{}")
    with pytest.raises(HXError, match="integrity"):
        selected_policy(tmp_path)
