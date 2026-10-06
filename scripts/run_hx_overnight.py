"""Bounded HX-only overnight stages with quota checks and a global usage ledger."""
import argparse
import json
import os
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.runner import AUTH, BINARY, lock_sources, run_case
from scripts.overnight_limits import account_usage, can_start
from scripts.run_hx_improvement import operational_failure


def locked_json(path):
    value = json.loads(path.read_text())
    lock = path.with_name(path.stem + ".lock.json")
    if sha(path) != json.loads(lock.read_text())["sha256"]:
        raise RuntimeError(f"Plan lock mismatch: {path}")
    return value


def ledger(envelope, plan):
    v2 = json.loads(Path(".hx/improvement-v2/results.json").read_text())
    used = max(0, v2["tokens"] - plan["baseline_improvement_v2_reported_tokens"])
    rows = []
    registry = locked_json(envelope / "experiments.json")
    incomplete = []
    for entry in registry["roots"]:
        root = Path(entry["root"]).resolve()
        for directory in ("search-history", "heldout-results"):
            for file in (root / "experiments" / directory).glob("*/score.json"):
                score = json.loads(file.read_text())
                rows.append({"stage": entry["stage"], "root": str(root), **score})
                used += score["observed_tokens"]
        # Account for retained interrupted runs with usage but no scored result.
        for descriptor in (root / "experiments").glob("*/**/state/native-state.json"):
            trial = descriptor.parent.parent
            if (trial / "score.json").exists():
                continue
            from benchmarks.polybench.state import trial_store
            runs = trial_store(root, trial).list()
            used += sum(r["observed_tokens"] for r in runs)
            if runs:
                incomplete.append({"stage": entry["stage"], "trial": str(trial),
                                   "run_ids": [r["id"] for r in runs]})
    value = {"updated": time.time(), "additional_reported_tokens": used,
             "max_additional_reported_tokens": plan["max_additional_reported_tokens"],
             "prior_pending_v2_tokens": v2["tokens"] - plan["baseline_improvement_v2_reported_tokens"],
             "rows": rows, "retained_unscored_attempts": incomplete,
             "development_trials": sum(r["stage"] == "development" for r in rows + incomplete),
             "evaluation_trials": sum(r["stage"] == "evaluation" for r in rows + incomplete)}
    write(envelope / "ledger.json", value)
    return value


def budget_guard(plan, usage, trial_tokens=600000, now=None):
    now = time.time() if now is None else now
    if now + 900 >= plan["deadline"]:
        raise RuntimeError("Overnight deadline lacks a full bounded trial window")
    # Leave headroom for usage reported at model turn boundaries.
    if usage["additional_reported_tokens"] + trial_tokens + 150000 > plan["max_additional_reported_tokens"]:
        raise RuntimeError("Overnight token envelope lacks trial headroom")


def run(envelope, root):
    plan = locked_json(envelope / "plan.json")
    manifest = locked_json(root / "manifest.json")
    stage = manifest["stage"]
    if sha(envelope / "plan.json") != manifest["envelope_sha256"]:
        raise RuntimeError("Overnight envelope changed")
    if sha(root / "settings.toml") != manifest["settings_sha256"]:
        raise RuntimeError("Stage model budgets changed")
    if stage == "evaluation":
        frozen = json.loads((envelope / "final-runtime.json").read_text())
        for name, expected_hash in frozen["source_sha256"].items():
            if sha(Path(name)) != expected_hash:
                raise RuntimeError("Final evaluation runtime changed")
    expected = plan["development_cases"] if stage == "development" else plan["reserved_evaluation_cases"]
    if manifest["cases"] != expected:
        raise RuntimeError("Stage case order changed")
    for name, expected_hash in manifest["scheduler_files"].items():
        if sha(Path(name)) != expected_hash:
            raise RuntimeError("Overnight scheduling dependency changed: " + name)
    lock_sources(root)
    started = time.time()

    def guard():
        usage = ledger(envelope, plan)
        budget_guard(plan, usage)
        quota = account_usage(BINARY, AUTH)
        write(envelope / "quota.json", quota)
        if not can_start(quota):
            raise RuntimeError("Account usage near limit; wait for natural reset")
        if (envelope / "stop-after-case").exists() or (root / "stop-after-case").exists():
            raise RuntimeError("Operator stop at scored boundary")

    with FileLock(str(envelope / "controller.lock")).acquire(timeout=0):
        write(envelope / "controller.json", {"pid": os.getpid(), "started": started,
              "root": str(root), "stage": stage})
        try:
            for case in manifest["cases"]:
                folder = "search-history" if stage == "development" else "heldout-results"
                score = root / "experiments" / folder / ("full-" + case + "-1/score.json")
                if score.exists():
                    continue
                usage = ledger(envelope, plan)
                limit = plan["max_new_development_trials"] if stage == "development" else plan["max_final_hx_only_evaluation_trials"]
                if usage[stage + "_trials"] >= limit:
                    raise RuntimeError("Stage trial envelope exhausted")
                guard()
                result = run_case(root, case, "full", start_guard=guard)
                value = ledger(envelope, plan)
                rows = [r for r in value["rows"] if r["root"] == str(root)]
                write(root / "results.json", {"stage": stage, "scored": len(rows),
                    "planned": len(manifest["cases"]), "rows": rows,
                    "official_resolved": sum(bool(r["official_resolved"]) for r in rows)})
                write(root / "experiments/report.json", {"rows": rows,
                    "planned_trials": len(manifest["cases"]), "mode": "HX-only " + stage,
                    "complete": len(rows) == len(manifest["cases"])})
                if operational_failure(result):
                    raise RuntimeError("Retained operational failure; investigate before more model work")
            write(root / "complete.json", {"finished": time.time(), "stage": stage})
        except Exception as exc:
            write(envelope / "stop.json", {"time": time.time(), "stage": stage,
                 "root": str(root), "error": str(exc)})
            raise
        finally:
            ledger(envelope, plan)
            write(envelope / "controller.exited.json", {"pid": os.getpid(), "time": time.time(),
                  "stage": stage})


if __name__ == "__main__":
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    parser = argparse.ArgumentParser()
    parser.add_argument("envelope", type=Path)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    run(args.envelope.resolve(), args.root.resolve())
