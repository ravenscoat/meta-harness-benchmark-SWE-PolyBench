import json

import pytest

from benchmarks.fresh import runner
from hx.models import HXError


def inputs(tmp_path):
    manifest = tmp_path / "manifest.json"
    cases = [{"id": f"domain-{i}", "task": "unused", "task_sha256": "unused",
              "split": "heldout", "groups": ["backend", "browser"]} for i in range(4)]
    manifest.write_text(json.dumps({"cases": cases}))
    validation = tmp_path / "validation.json"
    value = {"valid": True, "complete": True, "rows": [{"case": c["id"], "valid": True} for c in cases],
             "manifest_sha": runner.sha(manifest),
             "evaluators": {name: runner.sha(runner.HERE / name) for name in ("private_backend.py", "browser.cjs")}}
    validation.write_text(json.dumps(value))
    baseline = tmp_path / "baseline"
    (baseline / "src/hx").mkdir(parents=True)
    (baseline / "src/hx/engine.py").write_text("# archived fixture\n")
    (baseline / "source-sha256.json").write_text(json.dumps({
        "src/hx/engine.py": runner.sha(baseline / "src/hx/engine.py"),
    }))
    return manifest, validation, baseline


def test_prepare_requires_validated_matching_evaluators_and_manifest(tmp_path):
    manifest, validation, baseline = inputs(tmp_path)
    value = json.loads(validation.read_text())
    value["manifest_sha"] = "wrong"
    validation.write_text(json.dumps(value))
    with pytest.raises(HXError, match="different manifest"):
        runner.prepare(tmp_path / "campaign", manifest, validation, baseline, runner.HERE / "campaign.toml", 2)
    assert not (tmp_path / "campaign").exists()


def test_prepare_rejects_modified_archived_baseline(tmp_path):
    manifest, validation, baseline = inputs(tmp_path)
    (baseline / "src/hx/engine.py").write_text("altered")
    with pytest.raises(HXError, match="archived baseline changed"):
        runner.prepare(tmp_path / "campaign", manifest, validation, baseline, runner.HERE / "campaign.toml", 2)


def test_plan_pairs_all_three_arms_and_rejects_frozen_runtime_tampering(tmp_path, monkeypatch):
    manifest, validation, baseline = inputs(tmp_path)
    monkeypatch.setattr(runner, "environment", lambda: {"node": "fixture", "playwright": "fixture"})
    monkeypatch.setattr(runner, "copy_cache", lambda *_: None)
    monkeypatch.setattr(runner, "dependency_preflight", lambda *_: None)
    root = tmp_path / "campaign"
    runner.prepare(root, manifest, validation, baseline, runner.HERE / "campaign.toml", 2)
    plan = json.loads((root / "plan.json").read_text())
    assert len(plan["trials"]) == 24
    assert len({t["key"] for t in plan["trials"]}) == 24
    for domain in range(4):
        for repeat in (1, 2):
            assert {t["arm"] for t in plan["trials"] if t["case"]["id"] == f"domain-{domain}" and t["repeat"] == repeat} == {"single", "full", "improved"}
    assert [t["arm"] for t in plan["trials"][:3]] != [t["arm"] for t in plan["trials"][3:6]]
    (root / "runtime-improved/src/hx/engine.py").write_text("changed after freezing")
    with pytest.raises(HXError, match="frozen source changed"):
        runner.run(root, 15000000, 14400)
    assert not (root / "clock.json").exists()
