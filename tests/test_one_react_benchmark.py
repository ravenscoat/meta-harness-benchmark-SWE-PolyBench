import json

import pytest

from scripts import run_one_react_benchmark as batch


def test_budget_does_not_extend_deadline_or_allow_another_unfunded_call():
    plan = {"deadline": 2000, "max_reported_tokens": 600000}
    batch.guard_time_tokens(plan, 450000, 799)
    with pytest.raises(RuntimeError, match="trial window"):
        batch.guard_time_tokens(plan, 0, 800)
    with pytest.raises(RuntimeError, match="token headroom"):
        batch.guard_time_tokens(plan, 450001, 799)


def test_scored_react_identity_cannot_be_replaced(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    score = tmp_path / "score.json"
    score.write_text(json.dumps({"case": batch.CASE, "official_resolved": False}))
    with pytest.raises(RuntimeError, match="already has a coding score"):
        batch.validate_fresh({str(score): "hash"})


def test_exposed_react_task_cannot_be_called_fresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".hx/diagnostic"
    root.mkdir(parents=True)
    (root / "exposure.json").write_text(json.dumps({"cases": [batch.CASE]}))
    with pytest.raises(RuntimeError, match="has been exposed"):
        batch.validate_fresh({})


def test_interrupted_react_run_cannot_be_silently_retried(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = tmp_path / (".hx/previous/experiments/heldout-results/full-" + batch.CASE + "-1/state")
    state.mkdir(parents=True)
    (state / "native-state.json").write_text("{}")
    with pytest.raises(RuntimeError, match="Unscored React coding identity"):
        batch.validate_fresh({})
