"""Serial public-benchmark campaign; stop only at sealed case boundaries."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from benchmarks.polybench.preflight import preflight
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.runner import VENDOR, lock_sources, propose, report, run_case


def run(root: Path):
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    experiment = root / "experiments"
    envelope = experiment / "envelope.json"
    if not envelope.exists():
        write(envelope, {"started": time.time(), "max_seconds": 86400,
                         "max_observed_tokens": 50_000_000, "driver_sha256": sha(Path(__file__))})
    limits = json.loads(envelope.read_text())
    if sha(Path(__file__)) != limits["driver_sha256"]:
        raise RuntimeError("campaign driver changed after starting")
    selection = json.loads((root / "selection.json").read_text())

    def check_boundary():
        if (experiment / "stop-after-case").exists():
            raise RuntimeError("operator stop at scored boundary; saved evidence retained")
        current = report(root)
        usage = sum(r["observed_tokens"] for r in current["rows"]) + current["proposer_tokens"]
        if usage >= limits["max_observed_tokens"] or time.time() - limits["started"] >= limits["max_seconds"]:
            raise RuntimeError("campaign envelope exhausted; do not alter task limits")

    def trials(split, arms):
        cases = [c for c in selection["cases"] if c["split"] == split]
        for index, case in enumerate(cases):
            rotated = arms[index % len(arms):] + arms[:index % len(arms)]
            for arm in rotated:
                check_boundary()
                score = run_case(root, case["id"], arm)
                message = (score["error"] or "").lower()
                if score["grader_error"] or any(t in message for t in ("usage limit", "rate limit", "websocket", "authentication",
                        "sandbox setup", "container command failed", "container codex exited")):
                    raise RuntimeError("operational failure: scheduling stopped; raw trial retained")

    for split in ("setup", "development", "evaluation"):
        check_boundary()
        print(json.dumps({"event": "phase.preflight", "split": split}), flush=True)
        preflight(root, VENDOR.resolve(), split)
        validations = [json.loads((root / "preflight" / c["id"] / "validation.json").read_text())
                       for c in selection["cases"] if c["split"] == split]
        if not all(v["valid"] for v in validations):
            raise RuntimeError("reference/environment gate failed; no task replacement or worker scoring")
        if split == "setup":
            trials("setup", ["single"])
    # All environments are validated before development models and source freezing.
    lock_sources(root)
    trials("development", ["single", "full"])
    check_boundary()
    propose(root)
    trials("development", ["tuned-sol"])
    trials("evaluation", ["single", "full", "tuned-sol"])
    write(experiment / "complete.json", {"finished": time.time(), "evaluation_trials": 60,
                                         "total_task_trials": 95})
    report(root)
    print(json.dumps({"event": "campaign.complete", "task_trials": 95}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    run(parser.parse_args().root.resolve())
