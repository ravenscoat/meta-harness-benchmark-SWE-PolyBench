import json
from pathlib import Path

import pytest

from hx.adapters import CodexAdapter
from hx.models import ProcessTimeout, Settings, Task, WorkerSummary


@pytest.mark.parametrize("complete,valid,expected", [
    (True, True, "recovered"), (False, True, "timeout"), (True, False, "invalid")])
def test_only_completed_valid_cli_result_can_survive_timeout(monkeypatch, tmp_path,
        complete, valid, expected):
    import hx.adapters as module
    monkeypatch.setattr(module.shutil, "which", lambda _: "codex")
    def execute(argv, workspace, env, logs, timeout, control, on_line, *args):
        logs.mkdir(exist_ok=True)
        result = {"summary": "Finished change", "tests_added": [], "limitations": [],
            "verification_commands": [["pytest", "tests"]]} if valid else {"bad": True}
        Path(logs / "result.json").write_text(json.dumps(result))
        on_line(json.dumps({"type": "turn.started"}))
        if complete:
            on_line(json.dumps({"type": "turn.completed", "usage": {}}))
        raise ProcessTimeout("CLI exit timed out")
    monkeypatch.setattr(module, "execute", execute)
    adapter = CodexAdapter(Settings())
    task = Task(id="timeout", repo=str(tmp_path), report="Fix a small observed behavior bug.")
    events = []
    def call():
        return adapter.run("implementer", task, tmp_path, {}, "instructions",
            WorkerSummary, tmp_path / "logs", lambda: None,
            lambda kind, data: events.append(kind), 1)
    if expected == "recovered":
        assert call()["summary"] == "Finished change"
        assert "worker.completed_after_timeout" in events
    else:
        with pytest.raises((ProcessTimeout, ValueError)):
            call()
