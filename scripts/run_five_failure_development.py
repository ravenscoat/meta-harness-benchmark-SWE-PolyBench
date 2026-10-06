"""Exactly five user-authorized, previously failed official-task development retries."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.metrics import aggregate
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.state import trial_store
from scripts.overnight_limits import account_usage, can_start

SOURCES = [
    ("huggingface__transformers-26164", "regression-gate-evaluation-v1"),
    ("mui__material-ui-23229", "one-react-evaluation-v2"),
    ("huggingface__transformers-16198", "overnight-evaluation-v1"),
    ("serverless__serverless-2842", "overnight-evaluation-v1"),
    ("keras-team__keras-19863", "improvement-v3"),
]


def eligible_failure(row):
    return (row.get("official_resolved") is False
        and bool((row.get("acceptance") or {}).get("candidate_commit"))
        and not row.get("candidate_patch_error") and not row.get("grader_error")
        and row.get("unobserved_acceptance_tests") == 0)


def guard_budget(plan, tokens, now, worker=False):
    if tokens + (150000 if worker else 750000) > plan["max_reported_tokens"]:
        raise RuntimeError("Batch reported-token headroom exhausted")
    if now + (630 if worker else 1830) >= plan["deadline"]:
        raise RuntimeError("Batch deadline lacks another bounded execution window")


def prepare(root):
    if root.exists() or VisibleVerifier.version != "polybench-public-tests@9":
        raise RuntimeError("Require a new root and corrected runtime @9")
    root.mkdir(parents=True)
    base = Path(".hx/regression-gate-evaluation-v1")
    for name in ("dataset.csv", "storage.json"):
        shutil.copyfile(base / name, root / name)
    settings = Path(".hx/worker-environment-development-v2/settings.toml")
    shutil.copyfile(settings, root / "settings.toml")
    selection = json.loads((base / "selection.json").read_text())
    selection["cases"] = []
    images, prior = {}, {}
    for key, name in SOURCES:
        source = Path(".hx") / name
        if sha(source / "dataset.csv") != sha(root / "dataset.csv"):
            raise RuntimeError("Tasks use different pinned datasets")
        metadata = next(c for c in json.loads((source / "selection.json").read_text())["cases"] if c["id"] == key)
        old = json.loads((source / "images.json").read_text())[key]
        gate = json.loads((source / "preflight" / key / "validation.json").read_text())
        if not gate["valid"] or gate["image_id"] != old["image_id"]:
            raise RuntimeError("Original environment gate invalid: " + key)
        failed = [p for folder in ("setup-results", "search-history", "heldout-results")
            for p in (source / "experiments" / folder).glob("*/score.json")
            if (row := json.loads(p.read_text())).get("case") == key and eligible_failure(row)]
        if not failed:
            raise RuntimeError("No observed official behavioral failure for selected task: " + key)
        prior[key] = {str(p.resolve()): sha(p) for p in failed}
        metadata["split"] = old["split"] = "development"
        selection["cases"].append(metadata)
        images[key] = old
        for directory, file in (("public", key + ".json"), ("preflight/" + key, "validation.json")):
            target = root / directory
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / directory / file, target / file)
    write(root / "selection.json", selection)
    write(root / "images.json", images)
    (root / "experiments").mkdir()
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    started = time.time()
    plan = {"cases": [key for key, _ in SOURCES], "previous_failures": prior,
        "started": started, "deadline": started + 10800, "max_trials": 5,
        "max_reported_tokens": 3500000, "workflow_target": 400000,
        "worker": "gpt-6.1-sol", "workflow": "single", "max_revisions": 1,
        "model_attempt_seconds": 600, "workflow_seconds": 1800,
        "runtime": VisibleVerifier.version, "historical_score_sha256": historical,
        "scheduler_sha256": {str(p.resolve()): sha(p) for p in
            (Path(__file__), Path("scripts/overnight_limits.py"))},
        "selection": "Five most recent distinct delivered-candidate official behavioral failures selected from retained runs; exclude patch rejection, grader failure, missing observations, and no-candidate outcomes.",
        "limitations": "User-authorized development retries on consumed tasks, not fresh evaluation. Prior worker/runtime differ; no causal gain or leaderboard claim. Token targets checked at turn boundaries and can overshoot. Unknown consumption stops additional trials. No credits purchased/redeemed. Exactly one new scored identity per task; no replacements, scored reruns or frozen-runtime edits."}
    write(root / "batch-plan.json", plan)
    write(root / "batch-plan.lock.json", {"sha256": sha(root / "batch-plan.json")})
    runner.lock_sources(root)


def validate(root, plan):
    if sha(root / "batch-plan.json") != json.loads((root / "batch-plan.lock.json").read_text())["sha256"]:
        raise RuntimeError("Batch plan changed")
    for name, expected in {**plan["historical_score_sha256"], **plan["scheduler_sha256"]}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError("Sealed file changed: " + name)
    runner.lock_sources(root)


def usage(root):
    rows = [json.loads(p.read_text()) for p in sorted((root / "experiments/search-history").glob("*/score.json"))]
    tokens, incomplete = sum(r["observed_tokens"] for r in rows), []
    for descriptor in (root / "experiments/search-history").glob("*/state/native-state.json"):
        trial = descriptor.parent.parent
        if not (trial / "score.json").exists():
            runs = trial_store(root, trial).list()
            tokens += sum(r["observed_tokens"] for r in runs)
            incomplete.extend(r["id"] for r in runs)
    return rows, tokens, incomplete


def report(root, plan):
    rows, tokens, incomplete = usage(root)
    result = {"planned_trials": 5, "scored": len(rows), "complete": len(rows) == 5,
        "rows": rows, "reported_tokens": tokens, "retained_unscored_runs": incomplete,
        "official_resolved": sum(bool(r["official_resolved"]) for r in rows),
        "workflow_success": sum(bool(r["task_success"]) for r in rows),
        "metrics": aggregate(rows, time.time() - plan["started"]), "limitations": plan["limitations"]}
    write(root / "results.json", result)
    write(root / "experiments/report.json", result)
    return result


def run(root):
    plan = json.loads((root / "batch-plan.json").read_text())
    validate(root, plan)
    original = runner.PolyEngine
    def quota():
        current = account_usage(runner.BINARY, runner.AUTH)
        write(root / "quota.json", current)
        return can_start(current)
    def worker_guard():
        _, tokens, _ = usage(root)
        guard_budget(plan, tokens, time.time(), worker=True)
        validate(root, plan)
        if not quota():
            raise RuntimeError("Quota blocks additional model work; no credits used")
    class GuardedEngine(original):
        def _worker(self, *args, **kwargs):
            worker_guard()
            return super()._worker(*args, **kwargs)
    with FileLock(".hx/single-evaluation-controller.lock").acquire(timeout=0):
        write(root / "controller.json", {"pid": os.getpid(), "started": time.time()})
        runner.PolyEngine = GuardedEngine
        try:
            for key in plan["cases"]:
                validate(root, plan)
                rows, tokens, incomplete = usage(root)
                if any(r["case"] == key for r in rows):
                    continue
                if incomplete:
                    raise RuntimeError("Interrupted coding identity retained; no silent retry")
                if any(r.get("usage_known") is False for r in rows):
                    raise RuntimeError("Interrupted model consumption unknown; stop at scored boundary")
                guard_budget(plan, tokens, time.time())
                while not quota():
                    guard_budget(plan, tokens, time.time())
                    write(root / "experiments/phase.json", {"phase": "waiting_for_quota", "case": key, "updated": time.time()})
                    time.sleep(30)
                runner.run_case(root, key, "full", start_guard=worker_guard)
                result = report(root, plan)
                validate(root, plan)
                print(json.dumps({"event": "five-task.scored", "scored": result["scored"],
                    "official_resolved": result["official_resolved"], "case": key}), flush=True)
            write(root / "complete.json", {"time": time.time(), "trials": 5})
        except Exception as exc:
            write(root / "stop.json", {"time": time.time(), "error": str(exc)})
            raise
        finally:
            report(root, plan)
            write(root / "score-lock.json", {str(p.relative_to(root)): sha(p)
                for p in (root / "experiments/search-history").glob("*/score.json")})
            write(root / "controller.exited.json", {"pid": os.getpid(), "time": time.time()})
            runner.PolyEngine = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    root = args.root.resolve()
    if args.prepare:
        prepare(root)
    run(root)


if __name__ == "__main__":
    main()
