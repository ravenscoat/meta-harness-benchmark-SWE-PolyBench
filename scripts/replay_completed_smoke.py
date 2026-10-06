"""Model-free replay of a preserved completed CLI result, under a new identity."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from hx.config import canonical, load_settings, load_task
from hx.engine import Engine
from hx.models import WorkerSummary
from hx.store import Store, atomic_write


def main():
    old_root = Path(".hx/single-luna-live-v1").resolve()
    old_score = (old_root / "result.json").read_bytes()
    old = json.loads(old_score)
    native = Path(old["native_state"]).parent
    source = native / "state/runs" / old["run_id"] / "steps/implement/attempt-1/workspace"
    final = source.parent / "result.json"
    summary = WorkerSummary.model_validate_json(final.read_bytes())
    target = Path(".hx/single-luna-replay-v1").resolve()
    target.mkdir(exist_ok=False)
    staging = Path("/opt/hx-polybench-runtime/v1/state/single-luna-replay-v1")
    staging.mkdir(exist_ok=False)
    copied = staging / "preserved-worker"
    shutil.copytree(source, copied)
    subprocess.run(["git", "-C", str(copied), "add", "--all"], check=True)
    patch = subprocess.check_output(["git", "-C", str(copied), "diff", "--cached", "--binary"])
    atomic_write(target / "replayed.patch", patch)
    class ReplayAdapter:
        name = "completed-cli-replay"
        def run(self, role, task, workspace, *args):
            assert role == "implementer"
            subprocess.run(["git", "-C", str(workspace), "apply", "--binary", "-"],
                input=patch, check=True)
            return summary.model_dump()
    settings = load_settings(Path("hx.toml")).model_copy(update={"adapter": "fake", "max_revisions": 0})
    task = load_task(native / "fixture/tasks/missing-task.json")
    engine = Engine(Store(staging / "state"), settings, ReplayAdapter())
    run = engine.create(task)
    result = engine.execute(run["id"])
    assert (old_root / "result.json").read_bytes() == old_score
    atomic_write(target / "recovery.json", canonical({
        "status": result["status"], "handoff": result["handoff"], "error": result["error"],
        "model_calls": 0, "original_tokens": old["observed_tokens"],
        "original_failed_score_sha256": hashlib.sha256(old_score).hexdigest(),
        "original_structured_result_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "limitation": "Independent replay of one preserved live candidate, not a rerun or replacement of its failed attempt."}))
    shutil.copytree(staging / "state/runs", target / "runs")
    print(json.dumps({"status": result["status"], "error": result["error"]}))


if __name__ == "__main__":
    main()
