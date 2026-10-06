"""One explicitly consumed Svelte development attempt on the repaired runtime."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import sha, write
from scripts import run_one_react_benchmark as single

CASE = "sveltejs__svelte-728"


def prepare(root):
    if root.exists():
        raise RuntimeError("New development identity required")
    probe = Path(".hx/worker-environment-v1/report.json")
    if not json.loads(probe.read_text())["passed"] or VisibleVerifier.version != "polybench-public-tests@8":
        raise RuntimeError("Worker environment validation required")
    old = Path(".hx/sol-coverage-evaluation-v1")
    root.mkdir(parents=True)
    for name in ("dataset.csv", "storage.json"):
        shutil.copyfile(old / name, root / name)
    text = (old / "settings.toml").read_text().replace(
        "attempt_timeout_seconds = 240", "attempt_timeout_seconds = 600").replace(
        "run_timeout_seconds = 1200", "run_timeout_seconds = 1800")
    (root / "settings.toml").write_text(text)
    selection = json.loads((old / "selection.json").read_text())
    # Record an already consumed original evaluation task as development here.
    # Original files and scorer metadata remain intact in the old experiment.
    selection["cases"][0]["split"] = "development"
    write(root / "selection.json", selection)
    images = json.loads((old / "images.json").read_text())
    images[CASE]["split"] = "development"
    write(root / "images.json", images)
    for directory, name in (("public", CASE + ".json"), ("preflight/" + CASE, "validation.json")):
        destination = root / directory
        destination.mkdir(parents=True)
        shutil.copyfile(old / directory / name, destination / name)
    reproduction = Path(".hx/worker-environment-v1/public-reproduction-gist.json")
    sample = json.loads(reproduction.read_text())
    public_path = root / "public" / (CASE + ".json")
    public = json.loads(public_path.read_text())
    public["problem_statement"] += ("\n\nPublic reproduction linked by the original issue, cached for offline use. "
        "This is the reporter's example, not a solution or evaluator tests. Source: " + sample["source"] +
        "\n" + json.dumps(sample["files"], indent=2))
    write(public_path, public)
    shutil.copyfile(reproduction, root / "public-reproduction-gist.json")
    (root / "experiments").mkdir()
    inputs = [probe, reproduction, old / "results.json", old / "settings.toml", old / "selection.json",
              old / "images.json", root / "storage.json", root / "preflight" / CASE / "validation.json"]
    historical = {**single.history(), **{str(p.resolve()): sha(p) for p in inputs}}
    started = time.time()
    plan = {"cases": [CASE], "started": started, "not_before": 0,
        "deadline": started + 10800, "max_trials": 1, "max_reported_tokens": 800000,
        "per_trial_reported_token_target": 400000, "worker": "gpt-6.1-sol", "workflow": "single",
        "sol_review_calls": 0, "runtime_version": VisibleVerifier.version,
        "public_reproduction_source": sample["source"],
        "historical_score_sha256": historical, "historical_score_count": len(single.history()),
        "scheduler_sha256": {str(p.resolve()): sha(p) for p in (
            Path(__file__), Path(single.__file__), Path("scripts/run_paper_benchmark.py"),
            Path("scripts/overnight_limits.py"))},
        "rule": "One new development identity, one bounded public-feedback revision, no scored reruns or replacements. 600 seconds per model call and 1800 seconds per workflow; preparation does not consume model window but remains inside global deadline. Token limits checked at turn boundaries, can overshoot. No purchases or credit resets.",
        "limitations": "Already consumed Svelte task, public solution inspected previously. Selected development evidence, never fresh evaluation, paired improvement or leaderboard rank. Public build preparation is currently specific to this old Svelte layout. Larger attempt window also differs from prior attempt."}
    write(root / "batch-plan.json", plan)
    write(root / "batch-plan.lock.json", {"sha256": sha(root / "batch-plan.json")})
    runner.lock_sources(root)
    return plan


def report(root, plan):
    value = single_report(root, plan)
    value["limitations"] = plan["limitations"]
    value["runtime_version"] = plan["runtime_version"]
    write(root / "results.json", value)
    write(root / "experiments/report.json", value)
    (root / "experiments/REPORT.md").write_text(
        "# Svelte worker-environment development attempt\n\n" + json.dumps(value["metrics"], indent=2) +
        "\n\n" + plan["limitations"] + "\n")
    return value


single_report = single.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    root = args.root.resolve()
    if args.prepare:
        prepare(root)
    single.CASE = CASE
    single.report = report
    single.run(root)


if __name__ == "__main__":
    main()
