"""Idle-only, recorded-image cleanup. Does not delete source/state or use models."""

import json
import os
import subprocess
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.storage_lifecycle import recorded_images, release_images
from scripts.run_lean_three import prior_evidence


def run(output, apply=False):
    import docker

    if output.exists():
        raise RuntimeError("New maintenance record required")
    with FileLock(".hx/single-evaluation-controller.lock", timeout=0):
        processes = subprocess.check_output(["ps", "-eo", "pid,args", "--cols", "500"], text=True)
        for row in processes.splitlines()[1:]:
            fields = row.strip().split(None, 1)
            if (
                len(fields) == 2
                and int(fields[0]) != os.getpid()
                and fields[1].startswith("/opt/hx-polybench-venv/bin/python")
            ):
                raise RuntimeError("Benchmark helper still active; cleanup blocked")
        _, _, history = prior_evidence()
        client = docker.from_env(timeout=600)
        try:
            if client.containers.list(all=True):
                raise RuntimeError("Containers exist; idle cleanup blocked")
            output.mkdir(parents=True)
            records = recorded_images(Path(".hx"))
            write(
                output / "inventory.json",
                {
                    "records": records,
                    "historical_scores": history,
                    "apply": apply,
                    "models": 0,
                    "official_calls": 0,
                },
            )
            if apply:
                with (output / "events.jsonl").open("w") as log:

                    def emit(row):
                        log.write(json.dumps(row) + "\n")
                        log.flush()

                    outcomes = release_images(client, records, emit=emit)
            else:
                outcomes = []
            for name, value in history.items():
                if sha(Path(name)) != value:
                    raise RuntimeError("Historical score changed: " + name)
            write(
                output / "audit.json",
                {
                    "historical_scores_verified": len(history),
                    "outcomes": outcomes,
                    "applied": apply,
                    "models": 0,
                    "official_calls": 0,
                    "limitation": "Docker frees ext4 blocks; Windows free space requires VHD compaction.",
                },
            )
        finally:
            client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(args.output, args.apply)
