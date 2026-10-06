"""One locked MUI 23229 attempt, waiting for ordinary quota before model work."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.metrics import aggregate
from benchmarks.polybench.prepare import sha, write
from hx.config import load_settings
from scripts.overnight_limits import account_usage, can_start
from scripts.run_paper_benchmark import usage

CASE = "mui__material-ui-23229"
OLD = Path(".hx/harness-repair-evaluation-v1")


def history():
    return {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}


def validate_fresh(historical):
    for name in historical:
        row = json.loads(Path(name).read_text())
        if row.get("case", row.get("instance_id")) == CASE:
            raise RuntimeError("React case already has a coding score; do not rerun")
    for manifest in Path(".hx").glob("*/exposure.json"):
        if CASE in json.loads(manifest.read_text()).get("cases", []):
            raise RuntimeError("React case has been exposed; do not use as fresh evaluation")
    for descriptor in Path(".hx").glob("*/experiments/heldout-results/full-" + CASE + "-1/state/native-state.json"):
        raise RuntimeError("Unscored React coding identity retained: " + str(descriptor))


def guard_time_tokens(plan, tokens, now):
    if now + 1200 >= plan["deadline"]:
        raise RuntimeError("Single-task deadline lacks a bounded trial window")
    if tokens + 150000 > plan["max_reported_tokens"]:
        raise RuntimeError("Single-task token headroom exhausted")


def prepare(root, not_before):
    if root.exists():
        raise RuntimeError("New evidence root required")
    historical = history()
    validate_fresh(historical)
    runner.lock_sources(OLD)
    settings = load_settings(OLD / "settings.toml")
    if settings.workflow != "single" or settings.worker_model != "gpt-6-luna":
        raise RuntimeError("Expected frozen single-Luna settings")
    root.mkdir(parents=True)
    for name in ("dataset.csv", "storage.json", "settings.toml"):
        shutil.copyfile(OLD / name, root / name)
    selection = json.loads((OLD / "selection.json").read_text())
    selection["cases"] = [c for c in selection["cases"] if c["id"] == CASE]
    if len(selection["cases"]) != 1 or selection["cases"][0]["split"] != "evaluation":
        raise RuntimeError("Expected exact pinned evaluation case")
    write(root / "selection.json", selection)
    images = json.loads((OLD / "images.json").read_text())
    write(root / "images.json", {CASE: images[CASE]})
    for directory, file in (("public", CASE + ".json"), ("preflight/" + CASE, "validation.json")):
        target = root / directory
        target.mkdir(parents=True)
        shutil.copyfile(OLD / directory / file, target / file)
    (root / "experiments").mkdir()
    started = time.time()
    if not_before + 1200 >= started + 10800:
        raise RuntimeError("Scheduled start is outside the new three-hour envelope")
    plan = {"cases": [CASE], "started": started, "not_before": not_before,
        "deadline": started + 10800, "max_trials": 1, "max_reported_tokens": 600000,
        "per_trial_reported_token_target": settings.max_observed_tokens,
        "rule": "One fresh identity, at most one public-verification repair; no reruns, replacements, policy tuning or credit redemption. Token targets are checked at turn boundaries and can overshoot.",
        "worker": "gpt-6-luna", "workflow": "single", "sol_task_calls": 0,
        "selection_rule": "Exact user-authorized pending React evaluation case, originally selected by metadata order; no outcome filtering.",
        "runtime_version": "delivery-and-public-test-repair@1",
        "previous_campaign": str(OLD), "historical_score_sha256": historical,
        "scheduler_sha256": {str(p.resolve()): sha(p) for p in
            (Path(__file__), Path("scripts/overnight_limits.py"), Path("scripts/run_paper_benchmark.py"))}}
    write(root / "batch-plan.json", plan)
    write(root / "batch-plan.lock.json", {"sha256": sha(root / "batch-plan.json")})
    runner.lock_sources(root)
    return plan


def validate_locks(root, plan):
    if sha(root / "batch-plan.json") != json.loads((root / "batch-plan.lock.json").read_text())["sha256"]:
        raise RuntimeError("Plan lock mismatch")
    for name, expected in {**plan["historical_score_sha256"], **plan["scheduler_sha256"]}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError("Sealed file changed: " + name)
    runner.lock_sources(root)


def report(root, plan):
    rows, tokens, incomplete = usage(root)
    value = {"planned_trials": 1, "scored": len(rows), "complete": len(rows) == 1,
        "rows": rows, "reported_tokens": tokens, "retained_unscored_runs": incomplete,
        "metrics": aggregate(rows, time.time() - plan["started"]),
        "limitations": "One task held out within a known development repository; no baseline, causal gain or leaderboard claim. Wall time includes quota waiting."}
    write(root / "results.json", value)
    write(root / "experiments/report.json", value)
    metrics = value["metrics"]
    (root / "experiments/REPORT.md").write_text(
        "# One React task: MUI 23229\n\n" +
        f"Scored {len(rows)}/1.\n\n```json\n" + json.dumps(metrics, indent=2) + "\n```\n\n" +
        value["limitations"] + "\n", encoding="utf-8")
    return value


def run(root):
    plan = json.loads((root / "batch-plan.json").read_text())
    validate_locks(root, plan)
    original = runner.PolyEngine
    def guard():
        _, tokens, _ = usage(root)
        guard_time_tokens(plan, tokens, time.time())
        quota = account_usage(runner.BINARY, runner.AUTH)
        write(root / "quota.json", quota)
        if time.time() < plan["not_before"] or not can_start(quota):
            raise RuntimeError("Quota blocks model work; no credits used")
        validate_locks(root, plan)
    class GuardedEngine(original):
        def _worker(self, *args, **kwargs):
            guard()
            return super()._worker(*args, **kwargs)

    with FileLock(".hx/single-evaluation-controller.lock").acquire(timeout=0):
        write(root / "controller.json", {"pid": os.getpid(), "started": time.time(), "case": CASE})
        runner.PolyEngine = GuardedEngine
        try:
            report(root, plan)
            rows, _, incomplete = usage(root)
            if rows:
                return report(root, plan)
            if incomplete:
                raise RuntimeError("Interrupted identity retained; no silent coding retry")
            while True:
                guard_time_tokens(plan, 0, time.time())
                if time.time() >= plan["not_before"]:
                    quota = account_usage(runner.BINARY, runner.AUTH)
                    write(root / "quota.json", quota)
                    if can_start(quota):
                        break
                    next_check = min(plan["deadline"] - 1201, time.time() + 300)
                else:
                    next_check = plan["not_before"]
                write(root / "experiments/phase.json", {"phase": "waiting_for_quota",
                    "case": CASE, "next_quota_check": next_check, "updated": time.time()})
                print(json.dumps({"event": "quota.wait", "next_check": next_check}), flush=True)
                # Background controller owns this wait; no model call or reset-credit action.
                while time.time() < next_check:
                    time.sleep(min(30, next_check - time.time()))
            guard()
            result = runner.run_case(root, CASE, "full", start_guard=guard)
            validate_locks(root, plan)
            write(root / "complete.json", {"time": time.time(), "official_resolved": result["official_resolved"]})
            print(json.dumps({"event": "single_task.scored", **result}), flush=True)
        except Exception as exc:
            write(root / "stop.json", {"time": time.time(), "error": str(exc)})
            raise
        finally:
            report(root, plan)
            write(root / "score-lock.json", {str(p.relative_to(root)): sha(p)
                for p in (root / "experiments/heldout-results").glob("*/score.json")})
            write(root / "controller.exited.json", {"pid": os.getpid(), "time": time.time()})
            runner.PolyEngine = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--not-before", type=float, default=0)
    args = parser.parse_args()
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    root = args.root.resolve()
    if args.prepare:
        prepare(root, args.not_before)
    run(root)
