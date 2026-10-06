from __future__ import annotations

from pathlib import Path
from statistics import mean

from hx.config import canonical, load_task
from hx.engine import Engine
from hx.models import HXError
from hx.store import atomic_write


def benchmark(engine: Engine, task_dir: Path, repeats: int) -> dict:
    paths = sorted(task_dir.glob("*.json"))
    if not paths:
        raise HXError("no JSON task specifications found")
    rows = []
    for path in paths:
        task = load_task(path)
        for repeat in range(repeats):
            run = engine.create(task)
            run = engine.execute(run["id"])
            handoff = run["handoff"] or {}
            rows.append(
                {
                    "task": task.id,
                    "repeat": repeat + 1,
                    "run_id": run["id"],
                    "status": run["status"],
                    "verified": handoff.get("verified", False),
                    "reviewed": handoff.get("reviewed", False),
                    "seconds": run["elapsed_seconds"],
                    "observed_tokens": run["observed_tokens"],
                    "error": run["error"],
                }
            )
    report = {
        "adapter": engine.adapter.name,
        "fingerprint": engine.config["fingerprint"],
        "fixture_only": engine.adapter.name == "fake",
        "runs": rows,
        "ready_rate": mean(row["status"] == "ready_for_approval" for row in rows),
        "mean_seconds": mean(row["seconds"] for row in rows),
        "note": "Fake runs test the runtime only; they do not measure model success or benchmark superiority.",
    }
    atomic_write(engine.store.root / "benchmark.json", canonical(report))
    return report
