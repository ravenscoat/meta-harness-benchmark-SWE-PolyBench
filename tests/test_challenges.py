import json

import pytest
from pydantic import ValidationError

from hx.challenge_checks import backend_program, frontend_program
from hx.challenge_suite import CASES, materialize
from hx.config import load_task
from hx.optimization import Policy, report


def test_suite_has_separate_splits_and_reproducible_commits(tmp_path):
    path = materialize(tmp_path / "suite")
    manifest = json.loads(path.read_text())
    assert len(manifest["cases"]) == 12
    assert {c["split"] for c in manifest["cases"]} == {"search", "heldout"}
    for case in manifest["cases"]:
        task = load_task(__import__("pathlib").Path(case["task"]))
        assert task.base_commit == case["base_commit"]
        assert "frontend/src/**" in task.allowed_paths
        compile(
            (__import__("pathlib").Path(task.repo) / "backend/app.py").read_text(), "app.py", "exec"
        )
    with pytest.raises(Exception, match="empty"):
        materialize(tmp_path / "suite")


def test_private_program_selection_does_not_run_other_groups():
    assert backend_program(["version"]).endswith("test_version()")
    assert "latest tenant/query" in frontend_program(["search"])
    assert "rollback is isolated" not in frontend_program(["search"])
    assert all(groups for _, groups, _ in CASES.values())


def test_policy_cannot_request_arbitrary_paths_or_executable_code():
    with pytest.raises(ValidationError):
        Policy(
            name="bad",
            hypothesis="test isolation",
            instructions="",
            environment_snapshot=False,
            context_files=["../heldout.json"],
        )


def test_report_counts_acceptance_instead_of_ready_status(tmp_path):
    rows = [
        {
            "arm": "full",
            "split": "search",
            "case": "one",
            "task_success": False,
            "status": "ready_for_approval",
            "observed_tokens": 5,
            "seconds": 1,
        }
    ]
    result = report(tmp_path, rows, "full", 0)
    assert result["totals"]["search/full"]["passed"] == 0
