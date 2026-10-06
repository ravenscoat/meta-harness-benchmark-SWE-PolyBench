"""Preserve terminated benchmark evidence and seed a separate development batch."""
import json
import shutil
import time
from pathlib import Path

from benchmarks.polybench.prepare import sha, write


def prepare():
    old = Path(".hx/polybench-v1")
    new = Path(".hx/improvement-v1")
    if new.exists():
        raise RuntimeError("Improvement batch already exists; do not overwrite it")
    report_path = old / "experiments/report.json"
    report = json.loads(report_path.read_text())
    scores = {str(p.relative_to(old)): sha(p) for folder in
              ("setup-results", "search-history", "heldout-results")
              for p in (old / "experiments" / folder).glob("*/score.json")}
    assert len(scores) == len(report["rows"]) == 27
    write(old / "experiments/termination.json", {
        "reason": "User explicitly chose harness improvement over continuing the comparison campaign.",
        "controller_exited": True, "scored_trials": 27, "planned_trials": 51,
        "complete": False, "terminated": time.time(), "report_sha256": sha(report_path),
        "score_sha256": scores, "source_lock_sha256": sha(old / "experiments/source-lock.json"),
        "frozen_runtime_archive": "experiments/runtime-source-amendment-1",
        "live_checkout": "Now authorized for new development; old locks and runtime snapshots are retained unchanged.",
    })
    shutil.copy2(report_path, old / "experiments/report.at-termination.json")
    cases = ["keras-team__keras-19775", "keras-team__keras-19863", "keras-team__keras-18975"]
    new.mkdir()
    for name in ("dataset.csv", "storage.json"):
        shutil.copy2(old / name, new / name)
    selection = json.loads((old / "selection.json").read_text())
    selection["cases"] = [c for c in selection["cases"] if c["id"] in cases]
    assert len(selection["cases"]) == 3
    assert all(c["split"] == "development" for c in selection["cases"])
    write(new / "selection.json", selection)
    images = json.loads((old / "images.json").read_text())
    write(new / "images.json", {key: images[key] for key in cases})
    for key in cases:
        (new / "public").mkdir(exist_ok=True)
        shutil.copy2(old / "public" / (key + ".json"), new / "public" / (key + ".json"))
        (new / "preflight" / key).mkdir(parents=True)
        shutil.copy2(old / "preflight" / key / "validation.json", new / "preflight" / key / "validation.json")
    (new / "experiments").mkdir()
    (new / "settings.toml").write_text('''adapter = "codex"
worker_model = "gpt-6-luna"
judgment_model = "gpt-6.1-sol"
reasoning_effort = "medium"
max_revisions = 1
max_attempts = 1
max_resumes = 0
attempt_timeout_seconds = 300
verification_timeout_seconds = 180
run_timeout_seconds = 900
max_observed_tokens = 600000
max_log_bytes = 20000000
''', encoding="utf-8")
    write(new / "plan.json", {
        "purpose": "HX-only failure-driven development; not an unbiased benchmark or paired model comparison.",
        "cases": cases, "arm": "full", "started": time.time(), "max_seconds": 10800,
        "selection_reason": "One previously solved control, one observed behavioral failure, and one case with a prior baseline patch rejection. Selected from development evidence only.",
        "reported_token_budget_per_trial": 600000,
        "old_results": str(old / "experiments/report.at-termination.json"),
        "heldout_tasks": "All original evaluation tasks remain unused and reserved.",
        "score_policy": "New development attempts have separate identities and results; never replace old scores.",
        "scheduler_sha256": sha(Path("scripts/run_hx_improvement.py")),
    })
    write(new / "plan.lock.json", {"sha256": sha(new / "plan.json")})
    print(json.dumps({"terminated_trials": 27, "development_root": str(new), "cases": cases}))


if __name__ == "__main__":
    prepare()
