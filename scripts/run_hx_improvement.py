"""Three HX-only development probes, separate from the terminated comparison."""
import argparse
import json
import os
import time
from pathlib import Path

from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.runner import run_case


def operational_failure(score):
    """A bounded coding failure must not abort unrelated development probes."""
    if score["grader_error"]:
        return True
    message = (score["error"] or "").lower()
    return any(marker in message for marker in (
        "usage limit", "rate limit", "websocket", "authentication", "sandbox setup",
        "container command failed", "container codex exited", "invalid_json_schema",
    ))


def run(root):
    manifest_path = root / "plan.json"
    plan = json.loads(manifest_path.read_text())
    if sha(manifest_path) != json.loads((root / "plan.lock.json").read_text())["sha256"]:
        raise RuntimeError("Development plan changed")
    if sha(Path(__file__)) != plan["scheduler_sha256"]:
        raise RuntimeError("Development scheduler changed")
    for case in plan["cases"]:
        if (root / "stop-after-case").exists():
            return
        if time.time() - plan["started"] >= plan["max_seconds"]:
            raise RuntimeError("Development envelope exhausted")
        score_path = root / "experiments/search-history" / ("full-" + case + "-1/score.json")
        if not score_path.exists():
            run_case(root, case, "full")
        current = json.loads(score_path.read_text())
        scores = [json.loads(p.read_text()) for p in
                  (root / "experiments/search-history").glob("*/score.json")]
        write(root / "results.json", {
            "mode": "HX-only development probes; not a heldout benchmark",
            "planned": len(plan["cases"]), "scored": len(scores), "rows": scores,
            "tokens": sum(r["observed_tokens"] for r in scores),
            "official_resolved": sum(bool(r["official_resolved"]) for r in scores),
        })
        write(root / "experiments/report.json", {
            "rows": scores, "planned_trials": len(plan["cases"]),
            "complete": len(scores) == len(plan["cases"]),
            "mode": "development-only", "comparative_improvement_established": False,
        })
        if operational_failure(current):
            raise RuntimeError("Retained development failure; inspect before scheduling more work")
    write(root / "complete.json", {"finished": time.time(), "trials": len(plan["cases"])})


if __name__ == "__main__":
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    run(parser.parse_args().root.resolve())
