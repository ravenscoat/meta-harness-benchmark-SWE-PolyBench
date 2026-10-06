from pathlib import Path

import pytest
from pydantic import ValidationError

from hx.config import canonical, digest
from hx.git import check_scope, clone, git
from hx.models import GateError, Settings, Task
from hx.store import Store


@pytest.mark.parametrize(
    "path", ["../escape", "/absolute", "C:/escape", "backend\\app.py", "backend/../app.py"]
)
def test_task_path_escape_rejected(path):
    with pytest.raises(ValidationError):
        Task(id="test", repo=".", report="a valid task report", allowed_paths=[path])


def test_contract_does_not_coerce_budget():
    with pytest.raises(ValidationError):
        Settings(max_attempts="100")


def test_fingerprint_changes_with_prompt_text():
    assert digest({"prompt": "before"}) != digest({"prompt": "after"})
    assert canonical({"b": 2, "a": 1}) == canonical({"a": 1, "b": 2})


def test_protected_test_cannot_change(project, tmp_path):
    task = project["missing-task"]
    repo = clone(Path(task.repo), tmp_path / "clone", task.base_commit)
    with pytest.raises(GateError, match="protected path"):
        check_scope(repo, ["tests/test_existing.py"], task)


def test_clone_does_not_remove_original_remote(project, tmp_path):
    task = project["missing-task"]
    original = Path(task.repo)
    git(original, "remote", "add", "origin", "https://example.invalid/demo.git")
    copied = clone(original, tmp_path / "clone", task.base_commit)
    assert git(copied, "remote") == ""
    assert git(original, "remote") == "origin"


def test_event_order_persists_across_store_instances(tmp_path):
    store = Store(tmp_path / "state")
    run = store.create({}, {}, "base")
    for i in range(10):
        store.event(run["id"], "fixture", data={"i": i})
    reopened = Store(tmp_path / "state")
    events = reopened.events(run["id"])
    assert [event["data"]["i"] for event in events if event["type"] == "fixture"] == list(range(10))
    assert [event["seq"] for event in events] == sorted({event["seq"] for event in events})
