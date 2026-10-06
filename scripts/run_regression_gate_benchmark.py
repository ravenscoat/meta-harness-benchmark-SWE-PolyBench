"""One unused metadata-selected bug with the frozen public reproduction gate."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import sha, write
from hx.config import load_settings
from scripts import run_one_react_benchmark as single


def inventory(base=Path(".hx")):
    scores = {str(p.resolve()): sha(p) for p in base.glob("*/experiments/*/*/score.json")}
    exposures = {str(p.resolve()): sha(p) for p in base.glob("*/exposure.json")}
    used = set()
    for name in scores:
        row = json.loads(Path(name).read_text())
        used.add(row.get("case", row.get("instance_id")))
    for name in exposures:
        used.update(json.loads(Path(name).read_text()).get("cases", []))
    # An interrupted coding identity also consumes the task, even without a score.
    states = list(base.glob("*/experiments/*/*/state/native-state.json"))
    return scores, exposures, used, states


def select_case(cases, used, states):
    unavailable = {c["id"] for c in cases if any(c["id"] in p.parent.parent.name for p in states)}
    for case in cases:
        if (case["split"] == "evaluation" and case["category"] == "Bug Fix"
                and case["id"] not in used | unavailable):
            return case
    raise RuntimeError("No unused bug case remains in the pinned evaluation selection")


def prepare(root):
    if root.exists():
        raise RuntimeError("A new evaluation root is required")
    if VisibleVerifier.version != "polybench-public-tests@6":
        raise RuntimeError("Expected independently validated reproduction runtime @6")
    old = Path(".hx/polybench-v1")
    settings_source = Path(".hx/harness-repair-evaluation-v1/settings.toml")
    scores, exposures, used, states = inventory()
    selection = json.loads((old / "selection.json").read_text())
    case = select_case(selection["cases"], used, states)
    key = case["id"]
    validation_source = old / "preflight" / key / "validation.json"
    validation = json.loads(validation_source.read_text())
    images = json.loads((old / "images.json").read_text())
    if not validation["valid"] or validation["image_id"] != images[key]["image_id"]:
        raise RuntimeError("Selected environment is not valid; no replacement selected")
    settings = load_settings(settings_source)
    if (settings.workflow != "single" or settings.worker_model != "gpt-6-luna"
            or settings.max_revisions != 1 or settings.max_attempts != 1
            or settings.max_observed_tokens != 400000):
        raise RuntimeError("Expected unchanged bounded single-Luna settings")
    root.mkdir(parents=True)
    for name in ("dataset.csv", "storage.json"):
        shutil.copyfile(old / name, root / name)
    shutil.copyfile(settings_source, root / "settings.toml")
    selection["cases"] = [case]
    write(root / "selection.json", selection)
    write(root / "images.json", {key: images[key]})
    public = root / "public"
    public.mkdir()
    shutil.copyfile(old / "public" / (key + ".json"), public / (key + ".json"))
    preflight = root / "preflight" / key
    preflight.mkdir(parents=True)
    shutil.copyfile(validation_source, preflight / "validation.json")
    (root / "experiments").mkdir()
    started = time.time()
    inputs = [old / "selection.json", old / "images.json", validation_source,
              root / "storage.json", preflight / "validation.json"]
    scheduler = [Path(__file__), Path(single.__file__), Path("scripts/run_paper_benchmark.py"),
                 Path("scripts/overnight_limits.py")]
    plan = {"cases": [key], "started": started, "not_before": 0,
        "deadline": started + 10800, "max_trials": 1, "max_reported_tokens": 600000,
        "per_trial_reported_token_target": 400000,
        "worker": "gpt-6-luna", "workflow": "single", "sol_task_calls": 0,
        "selection_rule": "First unused, unexposed Bug Fix evaluation case in original pinned metadata order; exclude any retained coding identity; no outcome filtering or replacement.",
        "runtime_version": VisibleVerifier.version,
        "historical_score_sha256": {**scores, **exposures, **{str(p.resolve()): sha(p) for p in inputs}},
        "scheduler_sha256": {str(p.resolve()): sha(p) for p in scheduler},
        "historical_score_count": len(scores),
        "rule": "One fresh task identity, one Luna implementer with at most one public-feedback repair. No rerun or extension. Preserve previous scores; private evaluator content never enters model context. Token reporting is at turn boundaries and can overshoot.",
        "metrics": ["official_resolution", "workflow_readiness", "public_reproduction_classification",
                    "patch_rejection", "missing_required_observations", "infrastructure_errors",
                    "reported_tokens", "workflow_seconds", "wall_seconds"],
        "limitations": "One selected task in a previously used development repository; no baseline, causal improvement or leaderboard claim. Red/green is not independent proof of issue completeness."}
    write(root / "batch-plan.json", plan)
    write(root / "batch-plan.lock.json", {"sha256": sha(root / "batch-plan.json")})
    runner.lock_sources(root)
    print(json.dumps({"event": "evaluation.frozen", "case": key,
                      "runtime": plan["runtime_version"], "previous_scores": len(scores)}), flush=True)


def report(root, plan):
    value = single_report(root, plan)
    value["limitations"] = plan["limitations"]
    value["runtime_version"] = plan["runtime_version"]
    write(root / "results.json", value)
    write(root / "experiments/report.json", value)
    (root / "experiments/REPORT.md").write_text(
        "# One fresh reproduction-gate evaluation\n\nCase: " + plan["cases"][0] +
        "\n\n```json\n" + json.dumps(value["metrics"], indent=2) + "\n```\n\n" +
        plan["limitations"] + "\n", encoding="utf-8")
    return value


single_report = single.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    root = args.root.resolve()
    if args.prepare or args.prepare_only:
        prepare(root)
    plan = json.loads((root / "batch-plan.json").read_text())
    single.CASE = plan["cases"][0]
    single.report = report
    if args.prepare_only:
        report(root, plan)
        single.validate_locks(root, plan)
        return
    single.run(root)


if __name__ == "__main__":
    main()
