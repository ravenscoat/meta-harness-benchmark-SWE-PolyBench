"""External user scope cap: preserve frozen coding runtime, stop at scored boundary."""

import json
import os
import signal
import time
from pathlib import Path

from benchmarks.polybench.prepare import sha, write


def scored_boundary(plan, amendment, scores):
    expected = plan["cases"][:10]
    if amendment["cases"] != expected or amendment["max_tasks"] != 10:
        raise RuntimeError("Scope cap must be the first ten original cases")
    ids = {s["case"] for s in scores}
    if not ids <= set(expected):
        raise RuntimeError("A task outside the authorized cap was scored")
    if len(ids) != len(scores):
        raise RuntimeError("Duplicate scored identities")
    return ids == set(expected)


def supervise(root):
    file = root / "ten-task-amendment.json"
    lock = root / "ten-task-amendment.lock.json"
    amendment = json.loads(file.read_text())
    plan = json.loads((root / "plan.json").read_text())
    if (
        sha(file) != json.loads(lock.read_text())["sha256"]
        or sha(root / "plan.json") != amendment["parent_plan_sha256"]
    ):
        raise RuntimeError("Scope amendment or parent plan changed")
    controller = json.loads((root / "controller.json").read_text())
    pid = controller["pid"]
    if pid != amendment["controller_pid"]:
        raise RuntimeError("Controller identity changed")
    write(root / "scope-supervisor.json", {"pid": os.getpid(), "target_pid": pid, "max_tasks": 10})
    published_count = -1
    while not (root / "controller.exited.json").exists():
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except FileNotFoundError:
            if (root / "controller.exited.json").exists():
                break
            raise RuntimeError("Controller disappeared without an exit receipt") from None
        if "-m scripts.run_coding_seventeen " not in cmd or str(root) not in cmd:
            raise RuntimeError("Target PID no longer matches the exact controller")
        paths = list(root.glob("tasks/*/experiments/heldout-results/*/score.json"))
        scores = [json.loads(p.read_text()) for p in paths]
        boundary = scored_boundary(plan, amendment, scores)
        if len(scores) != published_count:
            publish(root, scores, boundary)
            published_count = len(scores)
        if boundary:
            # Pause immediately before examining the exact completed boundary.
            os.kill(pid, signal.SIGSTOP)
            try:
                outside = [
                    p
                    for p in root.glob(
                        "tasks/*/experiments/heldout-results/*/state/native-state.json"
                    )
                    if p.relative_to(root).parts[1] not in amendment["cases"]
                ]
                write(
                    root / "scope-boundary.json",
                    {
                        "scored": 10,
                        "target_pid": pid,
                        "scores": {str(p.relative_to(root)): sha(p) for p in paths},
                        "outside_cap_native_identities": [str(p) for p in outside],
                        "time": time.time(),
                        "reason": "Explicit user ten-task cap",
                    },
                )
                os.kill(pid, signal.SIGINT)
            finally:
                os.kill(pid, signal.SIGCONT)
            break
        time.sleep(0.1)
    write(root / "scope-supervisor.exited.json", {"pid": os.getpid(), "time": time.time()})


def publish(root, scores, boundary):
    write(
        root / "scope-results.json",
        {
            "planned_trials": 10,
            "scored_trials": len(scores),
            "complete": boundary,
            "official_resolutions": sum(s["official_resolved"] for s in scores),
            "rows": scores,
            "reported_tokens_scored": sum(s["observed_tokens"] for s in scores),
            "original_plan_preserved": True,
        },
    )


if __name__ == "__main__":
    import fcntl
    import sys

    root = Path(sys.argv[1])
    with (root / "scope-supervisor.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervise(root)
