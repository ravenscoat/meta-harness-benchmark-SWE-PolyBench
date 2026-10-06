"""Two unused SWE-PolyBench evaluation cases, one frozen single-Luna harness."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.state import trial_store
from hx.config import load_settings
from hx.meta import settings_toml
from scripts.overnight_limits import account_usage, can_start

CASES = ["langchain-ai__langchain-4579", "mui__material-ui-18683"]
HISTORY = ["polybench-v1", "improvement-v1", "improvement-v2", "improvement-v3",
    "overnight-evaluation-v1"]


def prior_scores():
    files = []
    for name in HISTORY:
        files.extend((Path(".hx") / name / "experiments").glob("*/*/score.json"))
    return {str(p): sha(p) for p in files}


def validate_fresh(cases, historical):
    used = {json.loads(Path(p).read_text()).get("case") for p in historical}
    if set(cases) & used:
        raise RuntimeError("Evaluation case already has a coding attempt; do not rerun it")


def guard_budget(plan, tokens, now=None):
    now = time.time() if now is None else now
    if now + 1200 >= plan["deadline"]:
        raise RuntimeError("Batch lacks a bounded trial window")
    if tokens + 550000 > plan["max_reported_tokens"]:
        raise RuntimeError("Batch lacks token headroom for another worker call")


def prepare(root):
    if root.exists():
        raise RuntimeError("A new benchmark root is required")
    historical = prior_scores()
    validate_fresh(CASES, historical)
    old = Path(".hx/polybench-v1")
    selected = json.loads((old / "selection.json").read_text())
    selected["cases"] = [c for c in selected["cases"] if c["id"] in CASES]
    if len(selected["cases"]) != 2 or any(c["split"] != "evaluation" for c in selected["cases"]):
        raise RuntimeError("Expected two original evaluation cases")
    root.mkdir(parents=True)
    for name in ("dataset.csv", "storage.json"):
        shutil.copyfile(old / name, root / name)
    write(root / "selection.json", selected)
    images = json.loads((old / "images.json").read_text())
    write(root / "images.json", {c: images[c] for c in CASES})
    (root / "public").mkdir()
    (root / "experiments").mkdir()
    for case in CASES:
        shutil.copyfile(old / "public" / (case + ".json"), root / "public" / (case + ".json"))
        destination = root / "preflight" / case
        destination.mkdir(parents=True)
        shutil.copyfile(old / "preflight" / case / "validation.json", destination / "validation.json")
    settings = load_settings(Path("hx.toml")).model_copy(update={"workflow": "single", "adapter": "codex",
        "max_observed_tokens": 400000, "max_revisions": 1, "max_attempts": 1,
        "attempt_timeout_seconds": 240, "verification_timeout_seconds": 180,
        "run_timeout_seconds": 1200})
    (root / "settings.toml").write_bytes(settings_toml(settings))
    started = time.time()
    plan = {"cases": CASES, "started": started, "deadline": started + 7200,
        "max_reported_tokens": 1200000, "max_trials": 2,
        "selection_rule": "First unused Python LangChain and React MUI case in original metadata order; no outcome filtering.",
        "worker": "gpt-6-luna", "workflow": "single", "arm_label": "full is legacy storage name; settings select single Luna",
        "historical_score_sha256": historical,
        "scheduler_sha256": {str(p): sha(p) for p in [Path(__file__), Path("scripts/overnight_limits.py")]},
        "rule": "Freeze runtime before either evaluation; no tuning from evaluation outcomes; no old trial reruns."}
    write(root / "batch-plan.json", plan)
    write(root / "batch-plan.lock.json", {"sha256": sha(root / "batch-plan.json")})
    runner.lock_sources(root)


def usage(root):
    rows = [json.loads(p.read_text()) for p in (root / "experiments/heldout-results").glob("*/score.json")]
    tokens = sum(r["observed_tokens"] for r in rows)
    incomplete = []
    for descriptor in (root / "experiments/heldout-results").glob("*/state/native-state.json"):
        trial = descriptor.parent.parent
        if not (trial / "score.json").exists():
            runs = trial_store(root, trial).list()
            tokens += sum(r["observed_tokens"] for r in runs)
            incomplete.extend(r["id"] for r in runs)
    return rows, tokens, incomplete


def report(root):
    rows, tokens, incomplete = usage(root)
    for row in rows:
        row["classification"] = ("official_resolution" if row["official_resolved"] else
            "patch_rejected" if row.get("candidate_patch_error") else
            "grader_infrastructure_error" if row.get("grader_error") else
            "no_accepted_candidate" if not row["acceptance"]["candidate_commit"] else
            "required_tests_unobserved" if row["unobserved_acceptance_tests"] else
            "observed_required_test_failure")
    value = {"planned_trials": 2, "scored": len(rows), "complete": len(rows) == 2,
        "rows": rows, "reported_tokens": tokens, "retained_unscored_runs": incomplete,
        "official_resolved": sum(r["official_resolved"] for r in rows),
        "workflow_success": sum(r["task_success"] for r in rows),
        "limitations": "Two selected public evaluation tasks, no baseline or causal improvement claim. Turn-boundary token reporting may overshoot."}
    write(root / "results.json", value)
    write(root / "experiments/report.json", value)
    (root / "experiments/REPORT.md").write_text(
        "# Frozen single-Luna SWE-PolyBench evaluation\n\n" +
        f"Scored {len(rows)}/2; official resolved {value['official_resolved']}; complete HX successes {value['workflow_success']}.\n\n" +
        "Legacy arm name `full` stores these single-Luna attempts. See settings.toml and actor traces.\n")
    return value


def run(root):
    plan = json.loads((root / "batch-plan.json").read_text())
    if sha(root / "batch-plan.json") != json.loads((root / "batch-plan.lock.json").read_text())["sha256"]:
        raise RuntimeError("Batch plan changed")
    for name, expected in {**plan["scheduler_sha256"], **plan["historical_score_sha256"]}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError("Sealed input changed: " + name)
    runner.lock_sources(root)
    original = runner.PolyEngine
    def guard():
        _, tokens, _ = usage(root)
        guard_budget(plan, tokens)
        quota = account_usage(runner.BINARY, runner.AUTH)
        write(root / "quota.json", quota)
        if not can_start(quota):
            raise RuntimeError("Account limits block model work; no credits used")
        runner.lock_sources(root)
    class GuardedEngine(original):
        def _worker(self, *args, **kwargs):
            guard()
            return super()._worker(*args, **kwargs)
    runner.PolyEngine = GuardedEngine
    with FileLock(str(root / "controller.lock")).acquire(timeout=0):
        write(root / "controller.json", {"pid": os.getpid(), "started": time.time()})
        try:
            for case in plan["cases"]:
                score = root / "experiments/heldout-results" / ("full-" + case + "-1/score.json")
                if score.exists():
                    continue
                rows, _, incomplete = usage(root)
                if incomplete or len(rows) >= 2:
                    raise RuntimeError("Interrupted coding identity retained; no silent scored rerun")
                guard()
                result = runner.run_case(root, case, "full", start_guard=guard)
                report(root)
                if result.get("grader_error"):
                    raise RuntimeError("Scored grader infrastructure error; retain evidence and stop")
            write(root / "complete.json", {"time": time.time()})
        except Exception as exc:
            write(root / "stop.json", {"time": time.time(), "error": str(exc)})
            raise
        finally:
            value = report(root)
            write(root / "score-lock.json", {str(p.relative_to(root)): sha(p)
                for p in (root / "experiments/heldout-results").glob("*/score.json")})
            write(root / "controller.exited.json", {"pid": os.getpid(), "time": time.time()})
            runner.PolyEngine = original
    print(json.dumps(value))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    root = args.root.resolve()
    if args.prepare:
        prepare(root)
    run(root)
