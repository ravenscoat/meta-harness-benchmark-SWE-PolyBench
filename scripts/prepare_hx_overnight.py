"""Seed one explicit overnight stage without modifying prior evidence."""
import argparse
import json
import shutil
from pathlib import Path

from benchmarks.polybench.prepare import sha, write
from scripts.run_hx_overnight import ledger, locked_json


def prepare(envelope, root, stage):
    plan = locked_json(envelope / "plan.json")
    if root.exists():
        raise RuntimeError("Stage root already exists; never overwrite evidence")
    old = Path(".hx/polybench-v1")
    cases = plan["development_cases"] if stage == "development" else plan["reserved_evaluation_cases"]
    selected = json.loads((old / "selection.json").read_text())
    selected["cases"] = [c for c in selected["cases"] if c["id"] in cases]
    expected_split = "development" if stage == "development" else "evaluation"
    assert len(selected["cases"]) == len(cases)
    assert all(c["split"] == expected_split for c in selected["cases"])
    if stage == "evaluation":
        usage = ledger(envelope, plan)
        if usage["development_trials"] != plan["max_new_development_trials"] or any(
                r["stage"] == "development" for r in usage["retained_unscored_attempts"]):
            raise RuntimeError("Finish and audit all development attempts before reserved evaluation")
        freeze = envelope / "final-runtime.json"
        sources = list(Path("src/hx").glob("*.py")) + list(Path("src/hx/prompts").glob("*.md"))
        sources += list(Path("benchmarks/polybench").glob("*.py"))
        current = {p.as_posix(): sha(p) for p in sources}
        if freeze.exists():
            if json.loads(freeze.read_text())["source_sha256"] != current:
                raise RuntimeError("Final runtime changed after reserved evaluation freeze")
        else:
            write(freeze, {"source_sha256": current, "rule": "No tuning from reserved evaluation outcomes"})
    root.mkdir()
    for name in ("dataset.csv", "storage.json"):
        shutil.copy2(old / name, root / name)
    shutil.copy2(Path(".hx/improvement-v2/settings.toml"), root / "settings.toml")
    write(root / "selection.json", selected)
    images = json.loads((old / "images.json").read_text())
    write(root / "images.json", {key: images[key] for key in cases})
    (root / "public").mkdir()
    (root / "experiments").mkdir()
    for key in cases:
        shutil.copy2(old / "public" / (key + ".json"), root / "public" / (key + ".json"))
        (root / "preflight" / key).mkdir(parents=True)
        shutil.copy2(old / "preflight" / key / "validation.json", root / "preflight" / key / "validation.json")
    dependencies = ["scripts/run_hx_overnight.py", "scripts/overnight_limits.py",
                    "scripts/run_hx_improvement.py"]
    write(root / "manifest.json", {"stage": stage, "cases": cases,
        "envelope_sha256": sha(envelope / "plan.json"),
        "settings_sha256": sha(root / "settings.toml"),
        "scheduler_files": {name: sha(Path(name)) for name in dependencies},
        "policy": "HX only; source-preserving test-plan revisions and public-test replay",
        "prior_results": ".hx/improvement-v2/results.json",
        "evaluation_rule": "Freeze before reserved evaluation; never tune from its results."})
    write(root / "manifest.lock.json", {"sha256": sha(root / "manifest.json")})
    registry = envelope / "experiments.json"
    entries = locked_json(registry) if registry.exists() else {"roots": []}
    if registry.exists():
        shutil.copy2(registry, envelope / f"experiments.before-{root.name}.json")
        shutil.copy2(envelope / "experiments.lock.json", envelope / f"experiments.lock.before-{root.name}.json")
    entries["roots"].append({"stage": stage, "root": root.as_posix()})
    write(registry, entries)
    write(envelope / "experiments.lock.json", {"sha256": sha(registry)})
    print(json.dumps({"root": str(root), "stage": stage, "cases": cases}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("envelope", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("stage", choices=["development", "evaluation"])
    args = parser.parse_args()
    prepare(args.envelope, args.root, args.stage)
