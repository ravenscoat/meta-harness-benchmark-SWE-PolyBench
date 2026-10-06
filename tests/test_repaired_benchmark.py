import hashlib
import json
from pathlib import Path

from scripts import run_repaired_benchmark as module


def test_fresh_selection_excludes_consumed_and_reference_exposed_cases(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    old = Path(".hx/polybench-v1")
    old.mkdir(parents=True)
    old.joinpath("selection.json").write_text(json.dumps({"cases": [
        {"id": "lang-used", "split": "evaluation", "repo": "langchain-ai/langchain"},
        {"id": "lang-exposed", "split": "evaluation", "repo": "langchain-ai/langchain"},
        {"id": "lang-fresh", "split": "evaluation", "repo": "langchain-ai/langchain"},
        {"id": "react-fresh", "split": "evaluation", "repo": "mui/material-ui"}]}))
    consumed = Path(".hx/old/experiments/heldout-results/trial")
    consumed.mkdir(parents=True)
    consumed.joinpath("score.json").write_text('{"case":"lang-used","official_resolved":false}')
    exposed = Path(".hx/diagnostic")
    exposed.mkdir()
    exposed.joinpath("exposure.json").write_text('{"cases":["lang-exposed"]}')
    original = {"cases": module.batch.CASES, "prior": module.batch.prior_scores}
    captured = []
    def fake_prepare(root):
        root.mkdir()
        captured.extend(module.batch.CASES)
        root.joinpath("batch-plan.json").write_text('{"scheduler_sha256":{}}')
    monkeypatch.setattr(module.batch, "prepare", fake_prepare)
    try:
        module.prepare(Path(".hx/fresh"))
        assert captured == ["lang-fresh", "react-fresh"]
        plan = Path(".hx/fresh/batch-plan.json")
        lock = json.loads(Path(".hx/fresh/batch-plan.lock.json").read_text())
        assert lock["sha256"] == hashlib.sha256(plan.read_bytes()).hexdigest()
    finally:
        module.batch.CASES = original["cases"]
        module.batch.prior_scores = original["prior"]
